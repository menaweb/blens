"""Riesgo intrínseco y residual MAGERIT, acoplado a la madurez (§9.2).

Es el diferenciador del producto: **una única fuente de verdad**. La madurez que el
cliente declara en el checklist alimenta a la vez el índice de cumplimiento y la eficacia
de la salvaguarda en el riesgo residual. No hay dos números que mantener.

Para cada instancia de amenaza (activo `a`, amenaza `t`, dimensión `d`):

    V   = valor acumulado del activo en esa dimensión (§9.1)
    R0  = V × degradación × frecuencia                        (riesgo intrínseco)

    e(m) = eficacia de la madurez de la medida m (tabla configurable, §7.1)
    w(m) = peso de m sobre esa amenaza (biblioteca curada, `measure_threat_map.yaml`)

    factor_freq   = Π sobre m∈FREQ   de (1 − e(m)·w(m))
    factor_imp    = Π sobre m∈IMPACT de (1 − e(m)·w(m))

    R_residual = V × degradación × factor_imp × frecuencia × factor_freq

La combinación es **multiplicativa** por defecto (defensa en profundidad: dos medidas
mediocres sobre la misma amenaza suman algo, pero cada vez menos). El modo `MEJOR`
(`1 − max(e·w)`) está disponible para quien prefiera no acumular: es la postura
conservadora que algunos consultores defienden, y se elige por parámetro, no por código.

**Ninguna combinación llega nunca a cero.** Un riesgo residual de 0 sería decir que la
amenaza ya no existe, y eso no lo firma un auditor. Los pesos del seed están topados a
0,7 precisamente por eso.

**Madurez no soportada** (`design/README_handoff.md`, pantalla 9): una salvaguarda cuya
madurez no tiene evidencia validada cuenta la mitad. Declarar no es demostrar.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal

from engines.risk_engine.graph import Activo, Dependencia, propagar

UNO = Decimal("1")
#: Seis decimales en los factores: no se ven, pero se multiplican entre sí.
Q_FACTOR = Decimal("0.000001")
#: Cuatro en los riesgos, que es lo que se guarda en NUMERIC y se enseña con uno o dos.
Q_RIESGO = Decimal("0.0001")

FREQ, IMPACT = "FREQ", "IMPACT"
MULTIPLICATIVA, MEJOR = "MULTIPLICATIVA", "MEJOR"
MAX, SUMA = "MAX", "SUMA"

NIVEL_MAXIMO = 5


def _q(valor: Decimal, paso: Decimal) -> Decimal:
    return valor.quantize(paso, rounding=ROUND_HALF_UP)


def _riesgo(valor: Decimal) -> Decimal:
    """Redondea un riesgo sin dejar que se convierta en cero por redondeo.

    Un residual positivo que cae por debajo de la resolución del informe se enseña como
    la unidad más pequeña, no como 0: la amenaza sigue ahí, aunque esté contenida. Solo
    vale cero lo que vale cero de verdad (un activo sin valor, o degradación nula).
    """
    redondeado = _q(valor, Q_RIESGO)
    return max(redondeado, Q_RIESGO) if valor > 0 else redondeado


@dataclass(frozen=True)
class Salvaguarda:
    """Una medida del ENS actuando sobre una amenaza (fila de `MeasureThreatMap`)."""

    threat_id: str
    measure_id: str
    aspect: str  # FREQ | IMPACT
    weight: Decimal
    #: Madurez declarada de la medida en este sistema (`MeasureAssessment`).
    nivel: int
    #: None = vale para todas las dimensiones de la amenaza.
    dim: str | None = None
    #: ¿Hay evidencia validada que sostenga ese nivel? (F4). Si no, cuenta la mitad.
    soportada: bool = True

    def eficacia(self, tabla: Mapping[int, Decimal]) -> Decimal:
        if self.nivel not in tabla:
            raise ValueError(f"Nivel de madurez sin eficacia definida: {self.nivel!r}")
        bruta = Decimal(tabla[self.nivel])
        return bruta if self.soportada else _q(bruta / 2, Q_FACTOR)


@dataclass(frozen=True)
class Amenaza:
    """Instancia de amenaza sobre un activo y una dimensión (`ThreatInstance`)."""

    asset_id: str
    threat_id: str
    dim: str
    #: Veces al año.
    frequency: Decimal
    #: Proporción del valor que se pierde si ocurre (0..1).
    degradation: Decimal


@dataclass(frozen=True)
class Aportacion:
    """Cuánto reduce una salvaguarda concreta. Es lo que se enseña en la pantalla 9."""

    measure_id: str
    aspect: str
    weight: Decimal
    nivel: int
    eficacia: Decimal
    soportada: bool
    #: e·w — la mordida que da esta medida sobre su factor.
    reduccion: Decimal


@dataclass(frozen=True)
class Riesgo:
    asset_id: str
    threat_id: str
    dim: str
    valor_acumulado: Decimal
    frequency: Decimal
    degradation: Decimal
    riesgo_intrinseco: Decimal
    factor_freq: Decimal
    factor_impacto: Decimal
    riesgo_residual: Decimal
    salvaguardas: tuple[Aportacion, ...]

    @property
    def reduccion_pct(self) -> Decimal:
        """Cuánto baja el riesgo respecto del intrínseco, en porcentaje."""
        if self.riesgo_intrinseco == 0:
            return Decimal("0.00")
        bajada = (UNO - self.riesgo_residual / self.riesgo_intrinseco) * 100
        return bajada.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Analisis:
    riesgos: tuple[Riesgo, ...]
    valores: Mapping[tuple[str, str], Decimal]

    def de(self, asset_id: str, threat_id: str, dim: str) -> Riesgo | None:
        return next(
            (
                r
                for r in self.riesgos
                if (r.asset_id, r.threat_id, r.dim) == (asset_id, threat_id, dim)
            ),
            None,
        )


def _aplicables(
    salvaguardas: Iterable[Salvaguarda], amenaza: Amenaza, aspecto: str
) -> list[Salvaguarda]:
    return sorted(
        (
            s
            for s in salvaguardas
            if s.threat_id == amenaza.threat_id
            and s.aspect == aspecto
            and (s.dim is None or s.dim == amenaza.dim)
        ),
        key=lambda s: (s.measure_id, s.weight),
    )


def _factor(
    aplicables: Sequence[Salvaguarda],
    eficacia_por_nivel: Mapping[int, Decimal],
    modo: str,
) -> tuple[Decimal, tuple[Aportacion, ...]]:
    """Factor de reducción de un aspecto y el desglose de quién lo aporta."""
    aportaciones = []
    for s in aplicables:
        eficacia = s.eficacia(eficacia_por_nivel)
        aportaciones.append(
            Aportacion(
                measure_id=s.measure_id,
                aspect=s.aspect,
                weight=Decimal(s.weight),
                nivel=s.nivel,
                eficacia=eficacia,
                soportada=s.soportada,
                reduccion=_q(eficacia * Decimal(s.weight), Q_FACTOR),
            )
        )

    if not aportaciones:
        return UNO, ()
    if modo == MEJOR:
        factor = UNO - max(a.reduccion for a in aportaciones)
    elif modo == MULTIPLICATIVA:
        factor = UNO
        for aportacion in aportaciones:
            factor *= UNO - aportacion.reduccion
    else:
        raise ValueError(f"Modo de combinación desconocido: {modo!r}")
    return _q(factor, Q_FACTOR), tuple(aportaciones)


def _residual(
    amenaza: Amenaza,
    valor: Decimal,
    salvaguardas: Sequence[Salvaguarda],
    eficacia_por_nivel: Mapping[int, Decimal],
    modo: str,
) -> Decimal:
    """Riesgo residual de una sola instancia, sin pasar por el grafo."""
    intrinseco = valor * Decimal(amenaza.degradation) * Decimal(amenaza.frequency)
    factor_freq, _ = _factor(_aplicables(salvaguardas, amenaza, FREQ), eficacia_por_nivel, modo)
    factor_imp, _ = _factor(_aplicables(salvaguardas, amenaza, IMPACT), eficacia_por_nivel, modo)
    return _riesgo(intrinseco * factor_freq * factor_imp)


def analizar(
    *,
    activos: Sequence[Activo],
    dependencias: Sequence[Dependencia],
    amenazas: Sequence[Amenaza],
    salvaguardas: Sequence[Salvaguarda],
    eficacia_por_nivel: Mapping[int, Decimal],
    modo: str = MULTIPLICATIVA,
) -> Analisis:
    """Punto de entrada del motor. Mismo input, mismo output, siempre.

    `eficacia_por_nivel` se pasa desde fuera a propósito: es la tabla configurable
    `MaturityEffectiveness` (§7.1), dato del catálogo, no una constante del código.
    """
    dimensiones = sorted({a.dim for a in amenazas})
    valores = propagar(activos, dependencias, dimensiones)

    riesgos = []
    for amenaza in sorted(amenazas, key=lambda a: (a.asset_id, a.threat_id, a.dim)):
        clave = (amenaza.asset_id, amenaza.dim)
        if clave not in valores:
            raise ValueError(
                f"La amenaza {amenaza.threat_id} apunta a un activo que no existe: "
                f"{amenaza.asset_id}."
            )
        valor = valores[clave]
        degradacion = Decimal(amenaza.degradation)
        frecuencia = Decimal(amenaza.frequency)
        intrinseco = valor * degradacion * frecuencia

        factor_freq, aporta_freq = _factor(
            _aplicables(salvaguardas, amenaza, FREQ), eficacia_por_nivel, modo
        )
        factor_imp, aporta_imp = _factor(
            _aplicables(salvaguardas, amenaza, IMPACT), eficacia_por_nivel, modo
        )

        riesgos.append(
            Riesgo(
                asset_id=amenaza.asset_id,
                threat_id=amenaza.threat_id,
                dim=amenaza.dim,
                valor_acumulado=valor,
                frequency=frecuencia,
                degradation=degradacion,
                riesgo_intrinseco=_riesgo(intrinseco),
                factor_freq=factor_freq,
                factor_impacto=factor_imp,
                riesgo_residual=_riesgo(intrinseco * factor_freq * factor_imp),
                salvaguardas=aporta_imp + aporta_freq,
            )
        )
    return Analisis(riesgos=tuple(riesgos), valores=valores)


def agregar_por_activo(riesgos: Sequence[Riesgo], modo: str = MAX) -> dict[str, Decimal]:
    """Riesgo residual por activo: `MAX` (peor caso) o `SUMA` (exposición total)."""
    if modo not in (MAX, SUMA):
        raise ValueError(f"Modo de agregación desconocido: {modo!r}")
    salida: dict[str, Decimal] = {}
    for riesgo in riesgos:
        actual = salida.get(riesgo.asset_id)
        if actual is None:
            salida[riesgo.asset_id] = riesgo.riesgo_residual
        elif modo == MAX:
            salida[riesgo.asset_id] = max(actual, riesgo.riesgo_residual)
        else:
            salida[riesgo.asset_id] = actual + riesgo.riesgo_residual
    return dict(sorted(salida.items()))


# --- Simulador inverso (§9.4) -----------------------------------------------------


@dataclass(frozen=True)
class Subida:
    measure_id: str
    nivel_actual: int
    nivel_propuesto: int


@dataclass(frozen=True)
class Simulacion:
    """Qué habría que subir para bajar de `objetivo`, y hasta dónde llega si no se puede."""

    alcanzable: bool
    riesgo_inicial: Decimal
    riesgo_final: Decimal
    subidas: tuple[Subida, ...]


def simular(
    *,
    amenaza: Amenaza,
    valor_acumulado: Decimal,
    salvaguardas: Sequence[Salvaguarda],
    eficacia_por_nivel: Mapping[int, Decimal],
    objetivo: Decimal,
    modo: str = MULTIPLICATIVA,
) -> Simulacion:
    """Simulador inverso: dado un riesgo objetivo, qué madurez mínima lo alcanza.

    Sube de nivel en nivel, eligiendo en cada paso la medida que más riesgo quita por
    nivel subido (a igualdad, la de código menor: el resultado no depende del orden de
    entrada). No busca el óptimo global —eso sería una mochila y el cliente no necesita
    la respuesta perfecta, necesita una defendible—, sino el camino más barato paso a
    paso, que es además el que se puede explicar en una frase.
    """
    estado = {s.measure_id: s for s in salvaguardas}

    def riesgo_con(actual: Mapping[str, Salvaguarda]) -> Decimal:
        return _residual(
            amenaza, Decimal(valor_acumulado), list(actual.values()), eficacia_por_nivel, modo
        )

    inicial = riesgo_con(estado)
    if inicial <= objetivo:
        return Simulacion(True, inicial, inicial, ())

    niveles_iniciales = {s.measure_id: s.nivel for s in salvaguardas}
    actual = inicial
    while actual > objetivo:
        mejor_id, mejor_riesgo = None, actual
        for measure_id, salvaguarda in sorted(estado.items()):
            if salvaguarda.nivel >= NIVEL_MAXIMO:
                continue
            candidato = dict(estado)
            candidato[measure_id] = replace(salvaguarda, nivel=salvaguarda.nivel + 1)
            riesgo = riesgo_con(candidato)
            if riesgo < mejor_riesgo:
                mejor_id, mejor_riesgo = measure_id, riesgo
        if mejor_id is None:
            break  # nada que subir, o subir ya no baja el riesgo
        estado[mejor_id] = replace(estado[mejor_id], nivel=estado[mejor_id].nivel + 1)
        actual = mejor_riesgo

    subidas = tuple(
        Subida(
            measure_id=measure_id,
            nivel_actual=niveles_iniciales[measure_id],
            nivel_propuesto=salvaguarda.nivel,
        )
        for measure_id, salvaguarda in sorted(estado.items())
        if salvaguarda.nivel != niveles_iniciales[measure_id]
    )
    return Simulacion(actual <= objetivo, inicial, actual, subidas)
