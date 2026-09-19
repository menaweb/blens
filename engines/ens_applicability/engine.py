"""Qué medidas y refuerzos aplican a un sistema concreto.

Puro y determinista: `(catálogo, categoría, niveles por dimensión) → resultado`. **No se
guarda en tabla** (§7.1): se deriva siempre, para que un cambio de categoría o de nivel no
deje datos viejos por ahí.

Las dos reglas del Anexo II (§3):

- `aplicacion-por = categoria`: aplica si la categoría del sistema está en sus props.
- `aplicacion-por = nivel-dimension`: aplica si **alguna** de las dimensiones que cita la
  medida tiene en este sistema un nivel que está en sus props. Por eso la categorización
  guarda el nivel de **cada** dimensión y no solo la categoría: mp.info.3 aplica por
  Integridad y Autenticidad, y una dimensión que no marca la categoría conserva su nivel
  (Anexo I.4.2).

Tres cosas que no son «aplica sí o no» y el producto tiene que distinguir:

- **Refuerzos obligatorios**: sus props dicen en qué categoría o nivel aplican.
- **Refuerzos opcionales**: los 41 que vienen sin props de aplicabilidad (§3.1, pendiente de
  contrastar con las tablas del RD). Se ofrecen, no se imponen.
- **Selecciones pendientes**: op.acc.5, op.acc.6, mp.com.4 y mp.s.2 obligan a elegir un
  refuerzo entre varios. Mientras no se elija, la DdA no está completa.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engines.oscal_io.models import (
    ORDEN_NIVEL,
    POR_CATEGORIA,
    POR_NIVEL_DIMENSION,
    Aplicabilidad,
    Catalog,
    Measure,
    Refuerzo,
)

NO_APLICA = "NA"


@dataclass(frozen=True)
class Perfil:
    """Lo que hay que saber del sistema para derivar la aplicabilidad."""

    categoria: str  # BASICA | MEDIA | ALTA
    niveles: dict[str, str]  # {'C': 'MEDIO', 'I': 'ALTO', 'T': 'NA', ...}

    def nivel(self, dimension: str) -> str:
        return self.niveles.get(dimension, NO_APLICA)

    @classmethod
    def desde_niveles(cls, niveles: dict[str, str]) -> Perfil:
        """Deriva la categoría del Anexo I: la más alta de las dimensiones."""
        mayor = max((ORDEN_NIVEL[n] for n in niveles.values()), default=0)
        categoria = {0: "BASICA", 1: "BASICA", 2: "MEDIA", 3: "ALTA"}[mayor]
        return cls(categoria=categoria, niveles=dict(niveles))


@dataclass(frozen=True)
class SeleccionPendiente:
    param_id: str
    measure_id: str
    nivel: str | None
    opciones: tuple[str, ...]
    usage: str


@dataclass(frozen=True)
class MedidaAplicable:
    measure_id: str
    marco: str
    familia: str
    motivo: str  # por qué aplica, en una frase para la DdA
    refuerzos_obligatorios: tuple[str, ...] = ()
    #: Los que vienen SIN props de aplicabilidad (§3.1): se ofrecen, no se imponen.
    refuerzos_opcionales: tuple[str, ...] = ()
    #: Declaran aplicabilidad y este sistema no la cumple (p. ej. un refuerzo de ALTA en
    #: un sistema Básico). No se piden, pero se enseñan: alguien puede querer adoptarlos.
    refuerzos_no_aplicables: tuple[str, ...] = ()
    selecciones: tuple[SeleccionPendiente, ...] = ()


@dataclass(frozen=True)
class Resultado:
    perfil: Perfil
    aplicables: tuple[MedidaAplicable, ...] = ()
    no_aplicables: tuple[tuple[str, str], ...] = field(default_factory=tuple)  # (id, motivo)

    @property
    def measure_ids(self) -> list[str]:
        return [m.measure_id for m in self.aplicables]

    @property
    def refuerzos_obligatorios(self) -> list[str]:
        return [r for m in self.aplicables for r in m.refuerzos_obligatorios]

    @property
    def selecciones_pendientes(self) -> list[SeleccionPendiente]:
        return [s for m in self.aplicables for s in m.selecciones]


def _dimensiones_activas(aplicabilidad: Aplicabilidad, perfil: Perfil) -> list[tuple[str, str]]:
    """Dimensiones de la medida cuyo nivel en este sistema está entre los que la activan."""
    return [
        (dim, perfil.nivel(dim))
        for dim in sorted(aplicabilidad.dimensiones)
        if perfil.nivel(dim) in aplicabilidad.niveles
    ]


def _evalua(aplicabilidad: Aplicabilidad, perfil: Perfil) -> tuple[bool, str]:
    """`(aplica, motivo)` para una medida o un refuerzo con props de aplicabilidad."""
    if aplicabilidad.aplicacion_por == POR_CATEGORIA:
        if perfil.categoria in aplicabilidad.categorias:
            return True, f"categoría {perfil.categoria}"
        return False, f"solo aplica en {', '.join(sorted(aplicabilidad.categorias))}"

    if aplicabilidad.aplicacion_por == POR_NIVEL_DIMENSION:
        activas = _dimensiones_activas(aplicabilidad, perfil)
        if activas:
            detalle = ", ".join(f"{dim}={nivel}" for dim, nivel in activas)
            return True, f"nivel de dimensión ({detalle})"
        exigido = ", ".join(sorted(aplicabilidad.niveles, key=lambda n: ORDEN_NIVEL[n]))
        dims = ", ".join(sorted(aplicabilidad.dimensiones))
        return False, f"ninguna de sus dimensiones ({dims}) alcanza {exigido or 'el nivel exigido'}"

    return False, "sin criterio de aplicabilidad declarado"


def _nivel_efectivo(medida: Measure, perfil: Perfil) -> str:
    """El mayor nivel entre las dimensiones que cita la medida. Elige qué selección toca."""
    niveles = [perfil.nivel(d) for d in medida.aplicabilidad.dimensiones]
    return max(niveles, key=lambda n: ORDEN_NIVEL[n], default=NO_APLICA)


def _refuerzos(
    medida: Measure, perfil: Perfil, selecciones: list[SeleccionPendiente]
) -> tuple[list[str], list[str], list[str]]:
    """Separa los refuerzos de una medida aplicable en obligatorios y opcionales.

    Solo se apartan los que son opción de una selección **que toca resolver aquí**. Un
    refuerzo que en Básica se elige y en Alta es obligatorio (mp.s.2.r2) tiene que salir
    como obligatorio en Alta, no desaparecer porque figure en el `select` de otro nivel.
    """
    en_seleccion = {opcion for seleccion in selecciones for opcion in seleccion.opciones}
    obligatorios: list[str] = []
    opcionales: list[str] = []
    no_aplicables: list[str] = []
    for refuerzo in medida.refuerzos:
        if refuerzo.id in en_seleccion:
            continue  # se resuelve eligiendo, no se impone
        if refuerzo.opcional:
            opcionales.append(refuerzo.id)
            continue
        aplica, _ = _evalua(refuerzo.aplicabilidad, perfil)
        (obligatorios if aplica else no_aplicables).append(refuerzo.id)
    return obligatorios, opcionales, no_aplicables


def _selecciones(medida: Measure, perfil: Perfil) -> list[SeleccionPendiente]:
    """Las disyunciones que toca resolver, según la categoría o el nivel del sistema."""
    nivel = _nivel_efectivo(medida, perfil)
    pendientes = []
    for param in medida.params:
        if param.nivel is not None and param.nivel != nivel:
            continue
        if param.categoria is not None and param.categoria != perfil.categoria:
            continue
        pendientes.append(
            SeleccionPendiente(
                param_id=param.id,
                measure_id=medida.id,
                nivel=param.nivel,
                opciones=param.choices,
                usage=param.usage,
            )
        )
    return pendientes


def aplicabilidad(catalogo: Catalog, perfil: Perfil) -> Resultado:
    """Deriva medidas aplicables, refuerzos y selecciones pendientes para un sistema."""
    aplicables: list[MedidaAplicable] = []
    no_aplicables: list[tuple[str, str]] = []

    for medida in catalogo.measures:
        aplica, motivo = _evalua(medida.aplicabilidad, perfil)
        if not aplica:
            no_aplicables.append((medida.id, motivo))
            continue
        selecciones = _selecciones(medida, perfil)
        obligatorios, opcionales, no_aplican = _refuerzos(medida, perfil, selecciones)
        aplicables.append(
            MedidaAplicable(
                measure_id=medida.id,
                marco=medida.marco,
                familia=medida.familia,
                motivo=motivo,
                refuerzos_obligatorios=tuple(obligatorios),
                refuerzos_opcionales=tuple(opcionales),
                refuerzos_no_aplicables=tuple(no_aplican),
                selecciones=tuple(selecciones),
            )
        )

    return Resultado(
        perfil=perfil, aplicables=tuple(aplicables), no_aplicables=tuple(no_aplicables)
    )


def refuerzos_de(catalogo: Catalog, measure_id: str) -> list[Refuerzo]:
    medida = catalogo.measure(measure_id)
    return list(medida.refuerzos) if medida else []
