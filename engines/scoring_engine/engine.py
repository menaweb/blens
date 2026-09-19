"""Índices de madurez y cumplimiento (CCN-STIC-815).

Puro y determinista: `(medidas valoradas, categoría) → porcentajes, deltas e índices`.
Sin Django y sin I/O, todo en `Decimal` con redondeo explícito (§15).

Las tres reglas de §8, que aquí no se reinterpretan:

- **L0-L5 a porcentaje** con la tabla de la 815: 0 / 10 / 50 / 80 / 90 / 100.
- **Objetivo por categoría**: Básica L2, Media L3, Alta L4. Una medida puede subir el
  suyo (nunca bajarlo por debajo del de la categoría: eso lo impone quien persiste).
- **Composición por el peor componente, no por la media.** Es la diferencia entre este
  motor y una hoja de cálculo: una familia con nueve medidas en L4 y una en L0 no está
  al 90 %, está al 0 %. Un auditor mira la que falta. La media se calcula igual, pero
  como dato informativo (`madurez_media`), nunca como el índice.

Dos índices distintos, que se confunden con facilidad:

- **Madurez**: dónde está la organización en términos absolutos (el % de la 815).
- **Cumplimiento**: cuánto del objetivo que exige su categoría ha alcanzado. Una Básica
  en L2 cumple al 100 % con una madurez del 50 %. Se topa en 100: pasarse del objetivo
  es bueno, pero no compensa otra medida por debajo.

**Madurez no soportada** (§10bis): una medida que alcanza su objetivo sin evidencia
validada no cuenta como alcanzada. No se le baja el nivel declarado —el cliente dice lo
que dice— pero el índice de cumplimiento la trata como si estuviera un nivel por debajo
del objetivo, y sale marcada. Mientras no exista el módulo de evidencias (F4) nadie pasa
`soportada=False`, así que el comportamiento es inerte pero ya está probado.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CIEN = Decimal("100")
#: Dos decimales en los porcentajes: es lo que se enseña y lo que se guarda en NUMERIC.
Q = Decimal("0.01")

#: Escala CMM de la CCN-STIC-815. Es el método, no el catálogo: no se configura por tenant.
PORCENTAJE_POR_NIVEL: Mapping[int, Decimal] = {
    0: Decimal("0"),
    1: Decimal("10"),
    2: Decimal("50"),
    3: Decimal("80"),
    4: Decimal("90"),
    5: Decimal("100"),
}

ETIQUETA_POR_NIVEL: Mapping[int, str] = {
    0: "inexistente",
    1: "inicial",
    2: "repetible",
    3: "definido",
    4: "gestionado",
    5: "optimizado",
}

#: Umbral mínimo de madurez por categoría (CCN-STIC-815, §3).
OBJETIVO_POR_CATEGORIA: Mapping[str, int] = {"BASICA": 2, "MEDIA": 3, "ALTA": 4}

VERDE, AMARILLO, ROJO, GRIS = "VERDE", "AMARILLO", "ROJO", "GRIS"


def redondear(valor: Decimal) -> Decimal:
    """Redondeo explícito y único: media vuelta arriba, dos decimales."""
    return valor.quantize(Q, rounding=ROUND_HALF_UP)


def porcentaje(nivel: int) -> Decimal:
    if nivel not in PORCENTAJE_POR_NIVEL:
        raise ValueError(f"Nivel de madurez fuera de la escala L0-L5: {nivel!r}")
    return PORCENTAJE_POR_NIVEL[nivel]


def objetivo_de(categoria: str) -> int:
    """Nivel exigido a un sistema de esa categoría. Sin categorizar, no se exige nada."""
    return OBJETIVO_POR_CATEGORIA.get(categoria, 0)


def semaforo(delta: int | None) -> str:
    """§8: verde si delta > −1, amarillo a un nivel, rojo a dos o más. Sin datos, gris.

    El prototipo `design/prototipos/Checklist de medidas.dc.html` usa exactamente estos
    cortes (`d >= 0` / `d === -1` / resto). La prosa del handoff dice «ámbar uno o dos»;
    manda el corte de §8 y del prototipo, que coinciden.
    """
    if delta is None:
        return GRIS
    if delta >= 0:
        return VERDE
    if delta == -1:
        return AMARILLO
    return ROJO


@dataclass(frozen=True)
class Medida:
    """Lo que hay que saber de una medida para puntuarla. Sale de `MeasureAssessment`."""

    measure_id: str
    marco: str
    familia: str
    #: None = nadie la ha valorado todavía. No es lo mismo que L0 declarado.
    madurez: int | None = None
    #: Objetivo propio; si falta, manda el de la categoría.
    objetivo: int | None = None
    aplica: bool = True
    #: ¿Tiene la evidencia obligatoria validada? (F4). Ver la nota del módulo.
    soportada: bool = True


@dataclass(frozen=True)
class ResultadoMedida:
    measure_id: str
    marco: str
    familia: str
    aplica: bool
    madurez: int | None
    objetivo: int
    #: % de la 815 del nivel declarado. Sin datos se puntúa 0: el indicador no redondea al alza.
    madurez_pct: Decimal
    cumplimiento_pct: Decimal
    delta: int | None
    semaforo: str
    sin_datos: bool
    #: Alcanza el objetivo declarado pero no hay evidencia validada que lo sostenga.
    no_soportada: bool
    #: Puntos de cumplimiento que se ganarían llevándola al objetivo.
    puntos_a_ganar: Decimal

    @property
    def en_objetivo(self) -> bool:
        return self.aplica and self.delta is not None and self.delta >= 0 and not self.no_soportada


@dataclass(frozen=True)
class Indice:
    """Índice de un ámbito (el sistema entero, un marco o una familia)."""

    ambito: str
    clave: str
    medidas: int
    con_datos: int
    en_objetivo: int
    no_soportadas: int
    #: El **peor componente** (§8). Es el índice que se publica.
    madurez: Decimal
    cumplimiento: Decimal
    #: Informativo: la media aritmética. No se usa como índice.
    madurez_media: Decimal
    cumplimiento_medio: Decimal
    #: Qué medida marca el mínimo. Es la respuesta a «¿por qué estoy en ese número?».
    peor: str | None


@dataclass(frozen=True)
class Resultado:
    categoria: str
    objetivo_categoria: int
    medidas: tuple[ResultadoMedida, ...]
    sistema: Indice
    por_marco: dict[str, Indice]
    por_familia: dict[str, Indice]

    @property
    def brechas(self) -> tuple[ResultadoMedida, ...]:
        """«Dónde se pierde más»: lo que falta, de más caro a más barato.

        Ordena por puntos a ganar y, a igualdad, por código: dos ejecuciones con los
        mismos datos devuelven la misma lista.
        """
        pendientes = [m for m in self.medidas if m.aplica and not m.en_objetivo]
        return tuple(sorted(pendientes, key=lambda m: (-m.puntos_a_ganar, m.measure_id)))

    def medida(self, measure_id: str) -> ResultadoMedida | None:
        return next((m for m in self.medidas if m.measure_id == measure_id), None)


def _puntua(medida: Medida, objetivo_categoria: int) -> ResultadoMedida:
    objetivo = medida.objetivo if medida.objetivo is not None else objetivo_categoria
    if objetivo not in PORCENTAJE_POR_NIVEL:
        raise ValueError(f"Objetivo fuera de la escala L0-L5: {objetivo!r}")

    sin_datos = medida.madurez is None
    nivel = medida.madurez or 0
    madurez_pct = porcentaje(nivel)
    delta = None if sin_datos else nivel - objetivo

    if not medida.aplica:
        # Una medida que no aplica no puntúa ni estorba: se excluye de los índices.
        return ResultadoMedida(
            measure_id=medida.measure_id,
            marco=medida.marco,
            familia=medida.familia,
            aplica=False,
            madurez=medida.madurez,
            objetivo=objetivo,
            madurez_pct=redondear(madurez_pct),
            cumplimiento_pct=redondear(CIEN),
            delta=delta,
            semaforo=GRIS,
            sin_datos=sin_datos,
            no_soportada=False,
            puntos_a_ganar=Decimal("0.00"),
        )

    alcanza = not sin_datos and nivel >= objetivo
    no_soportada = alcanza and not medida.soportada

    # Sin evidencia validada, la medida no cuenta como alcanzada: se puntúa como si
    # estuviera un nivel por debajo del objetivo (§10bis). El nivel declarado no se toca.
    nivel_efectivo = max(objetivo - 1, 0) if no_soportada else nivel
    meta = porcentaje(objetivo)
    logrado = porcentaje(nivel_efectivo)
    cumplimiento = CIEN if meta == 0 else min(logrado / meta * CIEN, CIEN)

    return ResultadoMedida(
        measure_id=medida.measure_id,
        marco=medida.marco,
        familia=medida.familia,
        aplica=True,
        madurez=medida.madurez,
        objetivo=objetivo,
        madurez_pct=redondear(madurez_pct),
        cumplimiento_pct=redondear(cumplimiento),
        delta=delta,
        semaforo=semaforo(delta),
        sin_datos=sin_datos,
        no_soportada=no_soportada,
        puntos_a_ganar=redondear(CIEN - cumplimiento),
    )


def _indice(ambito: str, clave: str, filas: Sequence[ResultadoMedida]) -> Indice:
    aplicables = [f for f in filas if f.aplica]
    if not aplicables:
        # Sin medidas aplicables no hay nada que puntuar. Cero, no cien: un ámbito vacío
        # no está cumplido, está sin datos, y decirlo al revés engaña al cliente.
        return Indice(
            ambito=ambito,
            clave=clave,
            medidas=0,
            con_datos=0,
            en_objetivo=0,
            no_soportadas=0,
            madurez=Decimal("0.00"),
            cumplimiento=Decimal("0.00"),
            madurez_media=Decimal("0.00"),
            cumplimiento_medio=Decimal("0.00"),
            peor=None,
        )

    peor_fila = min(aplicables, key=lambda f: (f.cumplimiento_pct, f.madurez_pct, f.measure_id))
    total = Decimal(len(aplicables))
    return Indice(
        ambito=ambito,
        clave=clave,
        medidas=len(aplicables),
        con_datos=sum(1 for f in aplicables if not f.sin_datos),
        en_objetivo=sum(1 for f in aplicables if f.en_objetivo),
        no_soportadas=sum(1 for f in aplicables if f.no_soportada),
        madurez=min(f.madurez_pct for f in aplicables),
        cumplimiento=peor_fila.cumplimiento_pct,
        madurez_media=redondear(sum((f.madurez_pct for f in aplicables), Decimal("0")) / total),
        cumplimiento_medio=redondear(
            sum((f.cumplimiento_pct for f in aplicables), Decimal("0")) / total
        ),
        peor=peor_fila.measure_id,
    )


def _agrupar(filas: Sequence[ResultadoMedida], ambito: str, atributo: str) -> dict[str, Indice]:
    grupos: dict[str, list[ResultadoMedida]] = {}
    for fila in filas:
        grupos.setdefault(getattr(fila, atributo), []).append(fila)
    return {clave: _indice(ambito, clave, grupo) for clave, grupo in sorted(grupos.items())}


def puntuar(medidas: Iterable[Medida], categoria: str) -> Resultado:
    """Punto de entrada del motor: valoraciones + categoría → índices.

    El orden de entrada no importa: las medidas salen ordenadas por código y los grupos
    por clave, para que dos ejecuciones iguales den resultados idénticos.
    """
    objetivo_categoria = objetivo_de(categoria)
    filas = tuple(
        sorted(
            (_puntua(m, objetivo_categoria) for m in medidas),
            key=lambda f: f.measure_id,
        )
    )
    return Resultado(
        categoria=categoria,
        objetivo_categoria=objetivo_categoria,
        medidas=filas,
        sistema=_indice("sistema", categoria, filas),
        por_marco=_agrupar(filas, "marco", "marco"),
        por_familia=_agrupar(filas, "familia", "familia"),
    )
