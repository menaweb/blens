"""Estructuras del catálogo OSCAL del Anexo II, ya normalizadas para BLENS.

Todo es inmutable y sin dependencias: se puede construir en un test sin base de datos.
Los **ids OSCAL son la clave estable** (`op.exp.6`, `op.exp.6.r1`, `op.exp.6.req.2`);
nada en BLENS debe identificar una medida de otra forma.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Dimensiones ACIDA. El catálogo las nombra en castellano; dentro usamos el código.
DIMENSIONES = {
    "Confidencialidad": "C",
    "Integridad": "I",
    "Trazabilidad": "T",
    "Autenticidad": "A",
    "Disponibilidad": "D",
}

CATEGORIAS = ("BASICA", "MEDIA", "ALTA")
NIVELES = ("NA", "BAJO", "MEDIO", "ALTO")

#: Orden para comparar. NA es "no aplica", no un nivel más bajo.
ORDEN_CATEGORIA = {c: i + 1 for i, c in enumerate(CATEGORIAS)}
ORDEN_NIVEL = {n: i for i, n in enumerate(NIVELES)}

POR_CATEGORIA = "categoria"
POR_NIVEL_DIMENSION = "nivel-dimension"


@dataclass(frozen=True)
class RequirementItem:
    """Requisito atómico de una medida: el ancla de checks y evidencias."""

    id: str  # 'op.exp.6.req.2'
    label: str  # 'op.exp.6.2' — OJO: no es único entre medidas
    prose: str
    orden: int
    children: tuple[RequirementItem, ...] = ()

    def flatten(self) -> list[RequirementItem]:
        items = [self]
        for hijo in self.children:
            items.extend(hijo.flatten())
        return items


@dataclass(frozen=True)
class Aplicabilidad:
    """Las props `urn:es:ens` de una medida o refuerzo, tal cual vienen."""

    aplicacion_por: str | None = None
    categorias: frozenset[str] = frozenset()
    niveles: frozenset[str] = frozenset()
    dimensiones: frozenset[str] = frozenset()

    @property
    def sin_declarar(self) -> bool:
        """Sin props de aplicabilidad. En los refuerzos significa *opcional* (§3.1)."""
        return self.aplicacion_por is None


@dataclass(frozen=True)
class Refuerzo:
    id: str
    measure_id: str
    titulo: str
    aplicabilidad: Aplicabilidad
    requisitos: tuple[RequirementItem, ...] = ()

    @property
    def opcional(self) -> bool:
        return self.aplicabilidad.sin_declarar


@dataclass(frozen=True)
class SelectionParam:
    """Disyunción «R1 o R2…»: hay que elegir uno (op.acc.5, op.acc.6, mp.com.4, mp.s.2)."""

    id: str
    measure_id: str
    label: str
    usage: str
    choices: tuple[str, ...]
    how_many: str = "one"
    nivel: str | None = None
    categoria: str | None = None


@dataclass(frozen=True)
class Measure:
    id: str
    marco: str  # org | op | mp
    familia: str  # org, op.pl, mp.if…
    titulo: str
    aplicabilidad: Aplicabilidad
    overview: str = ""
    requisitos: tuple[RequirementItem, ...] = ()
    refuerzos: tuple[Refuerzo, ...] = ()
    params: tuple[SelectionParam, ...] = ()

    def items(self, *, incluir_refuerzos: bool = False) -> list[RequirementItem]:
        salida = [i for raiz in self.requisitos for i in raiz.flatten()]
        if incluir_refuerzos:
            salida += [i for r in self.refuerzos for raiz in r.requisitos for i in raiz.flatten()]
        return salida


@dataclass(frozen=True)
class Catalog:
    titulo: str
    version: str
    oscal_version: str
    last_modified: str
    remarks: str
    source_url: str
    measures: tuple[Measure, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_por_id", {m.id: m for m in self.measures})

    def measure(self, measure_id: str) -> Measure | None:
        return self._por_id.get(measure_id)  # type: ignore[attr-defined]

    @property
    def refuerzos(self) -> list[Refuerzo]:
        return [r for m in self.measures for r in m.refuerzos]

    @property
    def items(self) -> list[RequirementItem]:
        """Todos los requisitos atómicos, los de las medidas y los de sus refuerzos."""
        return [i for m in self.measures for i in m.items(incluir_refuerzos=True)]

    def ids(self) -> set[str]:
        """Todos los ids citables por la capa propia: medidas, refuerzos e items."""
        salida = {m.id for m in self.measures}
        salida |= {r.id for r in self.refuerzos}
        salida |= {i.id for i in self.items}
        salida |= {i.label for i in self.items}  # la capa propia referencia por label
        return salida
