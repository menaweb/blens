"""De cómo es el sistema del cliente a qué evidencias le va a pedir el auditor.

Puro y determinista (§10bis.3): `(hechos, categoría, niveles, DdA, plantillas) → requisitos`.
Mismo perfil, misma carpeta, hoy y dentro de un año. Nada de esto toca la base de datos:
`apps.profiling` y `apps.evidence` traen los datos, este módulo decide.

Las tres cosas que hace:

1. **Qué preguntar.** Una pregunta se enseña si su `show_if` se cumple. Si la condición
   depende de un hecho que todavía nadie ha emitido, la pregunta **no** se enseña: es una
   pregunta de seguimiento y su padre está sin responder.
2. **Qué hechos deja una respuesta.** Cada opción declara sus `emits`; el cuestionario es
   la única fuente de los `ProfileFact` (§7.2), y esta traducción es parte del motor para
   poder probarla sin Django.
3. **Qué evidencias se piden.** Una plantilla se instancia si su medida está en la DdA, su
   refuerzo está activo y su `applies_if` se cumple. Las alternativas de un mismo
   `option_group` se devuelven juntas y ordenadas: **basta una** (§4 M5).

Dos decisiones que se notan en el producto:

- **Sin el hecho no hay condición.** Una regla que cita un hecho que nadie ha emitido es
  falsa, no verdadera. La carpeta crece según avanza el perfilado, en vez de aparecer
  entera el primer día y llenarse de requisitos que luego no aplicaban.
- **Recalcular no borra.** `reconciliar` compara lo que había con lo que toca ahora y solo
  dice qué dar de alta y qué pasar a `FUERA_DE_ALCANCE`. Las evidencias ya subidas se
  quedan donde están (§10bis.3).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from .jsonlogic import evaluar, hechos_citados

__all__ = [
    "CATEGORIA_ORDEN",
    "Campo",
    "Contexto",
    "NIVEL_ORDEN",
    "Opcion",
    "Plantilla",
    "Pregunta",
    "Reconciliacion",
    "RequisitoDerivado",
    "ResultadoEvidencias",
    "contexto_de_datos",
    "derivar_requisitos",
    "hechos_de_respuesta",
    "preguntas_visibles",
    "reconciliar",
    "se_cumple",
]

#: Orden de las categorías del Anexo I, para las reglas que comparan con `>=`.
CATEGORIA_ORDEN = {"BASICA": 1, "MEDIA": 2, "ALTA": 3}
#: Orden de los niveles por dimensión. `NA` es 0: no influye y no dispara nada.
NIVEL_ORDEN = {"NA": 0, "BAJO": 1, "MEDIO": 2, "ALTO": 3}

DIMENSIONES = "CITAD"


# --- lo que el motor recibe ---------------------------------------------------------


@dataclass(frozen=True)
class Opcion:
    """Una respuesta posible. `emits` es lo que deja escrito en el perfil del sistema."""

    code: str
    label: str = ""
    emits: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Campo:
    """Columna de las preguntas de tipo LIST y casilla de las de tipo NUMBER."""

    code: str
    label: str = ""


@dataclass(frozen=True)
class Pregunta:
    code: str
    bloque: str = ""
    orden: int = 0
    tipo: str = "SINGLE"
    texto: str = ""
    show_if: Any = None
    opciones: tuple[Opcion, ...] = ()
    campos: tuple[Campo, ...] = ()
    #: Para TEXT, DATE y NUMBER sin campos: plantilla de hechos con `$value` dentro.
    emits: Mapping[str, Any] = field(default_factory=dict)
    #: Solo en las TOOL: qué función de seguridad cubre el producto declarado (EDR, SIEM…).
    funcion: str = ""
    minutos_estimados: int = 1

    @property
    def opciones_por_codigo(self) -> dict[str, Opcion]:
        return {opcion.code: opcion for opcion in self.opciones}


@dataclass(frozen=True)
class Plantilla:
    """Requisito de evidencia «tipo»: lo que pediría un auditor si se da la condición."""

    code: str
    measure: str
    titulo: str = ""
    tipo: str = ""
    refuerzo: str = ""
    option_group: str = ""
    preferencia: int = 0
    obligatoria: bool = True
    applies_if: Any = None
    vigencia_dias: int | None = None
    carpeta_paquete: str = ""
    generable: bool = False


@dataclass(frozen=True)
class Contexto:
    """Todo lo que hace falta saber del sistema para evaluar una regla."""

    categoria: str
    niveles: Mapping[str, str] = field(default_factory=dict)
    hechos: Mapping[str, Any] = field(default_factory=dict)
    #: Qué pregunta dejó cada hecho. Es la trazabilidad que verá el auditor (§10bis.4).
    origen: Mapping[str, str] = field(default_factory=dict)

    def nivel(self, dimension: str) -> str:
        return self.niveles.get(dimension, "NA")

    @property
    def datos(self) -> dict[str, Any]:
        """El contexto tal y como lo leen las reglas del seed."""
        return {
            "categoria": self.categoria,
            "categoria_orden": CATEGORIA_ORDEN.get(self.categoria, 0),
            "nivel": dict(self.niveles),
            "nivel_orden": _NivelOrden(self.niveles),
            "hechos": dict(self.hechos),
        }


class _NivelOrden(Mapping):
    """`nivel_orden.CITA` es el nivel más alto de las dimensiones que se citan.

    El seed escribe así las condiciones («si Confidencialidad, Integridad, Trazabilidad o
    Autenticidad llegan a MEDIO…») porque es como está redactado el Anexo II. Se resuelve
    al vuelo en lugar de precalcular las 31 combinaciones posibles.
    """

    def __init__(self, niveles: Mapping[str, str]) -> None:
        self._niveles = niveles

    def __getitem__(self, dimensiones: str) -> int:
        if not dimensiones or any(d not in DIMENSIONES for d in dimensiones):
            raise KeyError(dimensiones)
        return max(NIVEL_ORDEN.get(self._niveles.get(d, "NA"), 0) for d in dimensiones)

    def __iter__(self):
        return iter(DIMENSIONES)

    def __len__(self) -> int:
        return len(DIMENSIONES)


def contexto_de_datos(
    categoria: str,
    niveles: Mapping[str, str],
    hechos: Mapping[str, Any] | None = None,
    origen: Mapping[str, str] | None = None,
) -> Contexto:
    return Contexto(
        categoria=categoria,
        niveles=dict(niveles),
        hechos=dict(hechos or {}),
        origen=dict(origen or {}),
    )


# --- 1. qué preguntar ---------------------------------------------------------------


def se_cumple(regla: Any, contexto: Contexto) -> bool:
    """¿Se cumple la condición con lo que sabemos hoy del sistema?

    Sin regla, sí. Si cita un hecho que nadie ha emitido todavía, **no**: la condición no
    es falsa, es que aún no se puede decidir, y en producto eso se comporta igual.
    """
    if regla is None:
        return True
    if hechos_citados(regla) - set(contexto.hechos):
        return False
    return bool(evaluar(regla, contexto.datos))


def preguntas_visibles(preguntas: Iterable[Pregunta], contexto: Contexto) -> tuple[Pregunta, ...]:
    """Las preguntas que toca enseñar ahora mismo, en el orden del cuestionario."""
    visibles = [p for p in preguntas if se_cumple(p.show_if, contexto)]
    return tuple(sorted(visibles, key=lambda p: (p.bloque, p.orden, p.code)))


# --- 2. qué hechos deja una respuesta ------------------------------------------------


def hechos_de_respuesta(pregunta: Pregunta, valor: Any) -> dict[str, Any]:
    """Traduce el valor guardado de una respuesta a los hechos que deja en el perfil.

    - SINGLE y BOOL: el `emits` de la opción marcada.
    - MULTI: los `emits` de todas las marcadas. Si dos dejan la misma clave, el hecho pasa
      a tener varios valores, y las reglas lo comparan como conjunto (ver `jsonlogic`).
    - NUMBER y LIST: un hecho por campo; en LIST, la columna entera.
    - TEXT y DATE: el `emits` de la pregunta, con `$value` sustituido por la respuesta.
    - TOOL y VENDOR: el `emits` de la opción, si la hay, más la lista de productos
      declarados bajo `herramienta_<funcion>`, que es lo que enlaza con `SecurityComponent`
      y con las pistas por producto (§10bis.2b).
    """
    if valor is None:
        return {}

    hechos: dict[str, Any] = {}
    opciones = pregunta.opciones_por_codigo

    if pregunta.tipo in ("SINGLE", "BOOL"):
        opcion = opciones.get(_codigo(valor))
        if opcion:
            _acumular(hechos, opcion.emits, valor)

    elif pregunta.tipo == "MULTI":
        for codigo in _codigos(valor):
            opcion = opciones.get(codigo)
            if opcion:
                _acumular(hechos, opcion.emits, codigo)

    elif pregunta.tipo in ("TOOL", "VENDOR"):
        marcado = valor.get("opcion") if isinstance(valor, Mapping) else None
        for codigo in _codigos(marcado):
            opcion = opciones.get(codigo)
            if opcion:
                _acumular(hechos, opcion.emits, codigo)
        productos = _productos(valor)
        if productos and pregunta.funcion:
            hechos[f"herramienta_{pregunta.funcion.lower()}"] = productos

    elif pregunta.tipo == "NUMBER":
        for campo in pregunta.campos:
            numero = valor.get(campo.code) if isinstance(valor, Mapping) else valor
            if numero is not None:
                hechos[campo.code] = numero
        if not pregunta.campos:
            _acumular(hechos, pregunta.emits, valor)

    elif pregunta.tipo == "LIST":
        filas = valor if isinstance(valor, list) else []
        for campo in pregunta.campos:
            columna = [fila.get(campo.code) for fila in filas if isinstance(fila, Mapping)]
            hechos[campo.code] = [v for v in columna if v not in (None, "")]

    else:  # TEXT, DATE y cualquier tipo futuro que solo guarde un valor suelto
        _acumular(hechos, pregunta.emits, valor)

    return hechos


def _acumular(hechos: dict[str, Any], emits: Mapping[str, Any], valor: Any) -> None:
    """Añade los hechos de una opción, juntando los valores si la clave se repite."""
    for clave, emitido in (emits or {}).items():
        nuevo = valor if emitido == "$value" else emitido
        if clave not in hechos:
            hechos[clave] = list(nuevo) if isinstance(nuevo, list) else nuevo
            continue
        actuales = hechos[clave] if isinstance(hechos[clave], list) else [hechos[clave]]
        entrantes = nuevo if isinstance(nuevo, list) else [nuevo]
        for elemento in entrantes:
            if elemento not in actuales:
                actuales.append(elemento)
        hechos[clave] = actuales


def _codigo(valor: Any) -> str:
    if isinstance(valor, Mapping):
        return str(valor.get("opcion", ""))
    if isinstance(valor, bool):
        return "si" if valor else "no"
    return str(valor)


def _codigos(valor: Any) -> list[str]:
    if valor is None:
        return []
    if isinstance(valor, (list, tuple)):
        return [_codigo(v) for v in valor]
    return [_codigo(valor)]


def _productos(valor: Any) -> list[str]:
    """Nombres de los productos declarados en una pregunta TOOL o VENDOR."""
    if isinstance(valor, Mapping):
        crudos = valor.get("productos") or valor.get("producto") or []
    else:
        crudos = valor
    if isinstance(crudos, (str, Mapping)):
        crudos = [crudos]
    nombres = []
    for producto in crudos or []:
        nombre = producto.get("producto", "") if isinstance(producto, Mapping) else str(producto)
        if nombre:
            nombres.append(nombre)
    return nombres


# --- 3. qué evidencias se piden ------------------------------------------------------


@dataclass(frozen=True)
class RequisitoDerivado:
    """Una plantilla que este sistema sí tiene que cubrir, con por qué se le pide."""

    plantilla: Plantilla
    motivo: str
    #: Hechos que dispararon la condición, con su valor y la pregunta que los dejó.
    origen: Mapping[str, Any] = field(default_factory=dict)

    @property
    def code(self) -> str:
        return self.plantilla.code


@dataclass(frozen=True)
class ResultadoEvidencias:
    requisitos: tuple[RequisitoDerivado, ...] = ()
    #: `option_group` → códigos de plantilla ordenados por preferencia. Basta cubrir una.
    grupos: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    #: Medidas aplicables que se han quedado sin ninguna plantilla alcanzable.
    medidas_sin_evidencia: tuple[str, ...] = ()

    @property
    def codigos(self) -> frozenset[str]:
        return frozenset(requisito.code for requisito in self.requisitos)

    def por_medida(self) -> dict[str, tuple[RequisitoDerivado, ...]]:
        agrupado: dict[str, list[RequisitoDerivado]] = {}
        for requisito in self.requisitos:
            agrupado.setdefault(requisito.plantilla.measure, []).append(requisito)
        return {medida: tuple(lista) for medida, lista in agrupado.items()}


def derivar_requisitos(
    plantillas: Iterable[Plantilla],
    contexto: Contexto,
    medidas_aplicables: Iterable[str],
    refuerzos_activos: Iterable[str] = (),
) -> ResultadoEvidencias:
    """La carpeta de evidencias de este sistema: qué se le pide y por qué.

    `medidas_aplicables` y `refuerzos_activos` salen de la DdA (M2), no del catálogo: lo
    que el cliente ha marcado como no aplicable con justificación no pide evidencias.
    """
    medidas = set(medidas_aplicables)
    refuerzos = set(refuerzos_activos)
    plantillas = list(plantillas)

    requisitos: list[RequisitoDerivado] = []
    for plantilla in plantillas:
        if plantilla.measure not in medidas:
            continue
        if plantilla.refuerzo and plantilla.refuerzo not in refuerzos:
            continue
        if not se_cumple(plantilla.applies_if, contexto):
            continue
        requisitos.append(
            RequisitoDerivado(
                plantilla=plantilla,
                motivo=_motivo(plantilla, contexto),
                origen=_origen(plantilla, contexto),
            )
        )

    requisitos.sort(key=lambda r: (r.plantilla.measure, r.plantilla.preferencia, r.code))

    grupos: dict[str, list[Plantilla]] = {}
    for requisito in requisitos:
        if requisito.plantilla.option_group:
            grupos.setdefault(requisito.plantilla.option_group, []).append(requisito.plantilla)

    con_evidencia = {r.plantilla.measure for r in requisitos}
    return ResultadoEvidencias(
        requisitos=tuple(requisitos),
        grupos={
            grupo: tuple(p.code for p in sorted(lista, key=lambda p: (p.preferencia, p.code)))
            for grupo, lista in sorted(grupos.items())
        },
        medidas_sin_evidencia=tuple(sorted(medidas - con_evidencia)),
    )


def _motivo(plantilla: Plantilla, contexto: Contexto) -> str:
    """Una frase para el índice del paquete: por qué está este hueco en la carpeta."""
    partes = [
        f"la medida {plantilla.measure} aplica a un sistema de categoría {contexto.categoria}"
    ]
    if plantilla.refuerzo:
        partes.append(f"con el refuerzo {plantilla.refuerzo}")
    citados = sorted(hechos_citados(plantilla.applies_if))
    if citados:
        partes.append("y así se ha descrito el sistema: " + ", ".join(citados))
    return " ".join(partes)


def _origen(plantilla: Plantilla, contexto: Contexto) -> dict[str, Any]:
    """Trazabilidad pregunta → hecho → requisito, tal y como la pide §10bis.4."""
    hechos = {
        clave: contexto.hechos.get(clave) for clave in sorted(hechos_citados(plantilla.applies_if))
    }
    return {
        "hechos": hechos,
        "preguntas": sorted({contexto.origen[c] for c in hechos if c in contexto.origen}),
        "categoria": contexto.categoria,
        "niveles": dict(contexto.niveles),
    }


# --- recalcular sin romper nada ------------------------------------------------------


@dataclass(frozen=True)
class Reconciliacion:
    """Qué cambia en la carpeta cuando el cliente corrige una respuesta."""

    altas: tuple[str, ...] = ()
    #: Estaban y ya no tocan. **No se borran**: pasan a FUERA_DE_ALCANCE con lo que tengan.
    fuera_de_alcance: tuple[str, ...] = ()
    #: Estaban fuera de alcance y vuelven a pedirse, con sus evidencias de antes.
    reactivados: tuple[str, ...] = ()
    sin_cambio: tuple[str, ...] = ()

    @property
    def hay_cambios(self) -> bool:
        return bool(self.altas or self.fuera_de_alcance or self.reactivados)


FUERA_DE_ALCANCE = "FUERA_DE_ALCANCE"


def reconciliar(actuales: Mapping[str, str], derivados: Iterable[str]) -> Reconciliacion:
    """Compara la carpeta de hoy (`código → estado`) con la que toca ahora.

    Decide, no ejecuta: quien escribe en la base de datos es `apps.evidence`. Y nunca
    propone borrar, porque detrás de un requisito puede haber un fichero que costó
    conseguir (§10bis.3).
    """
    derivados = set(derivados)
    presentes = set(actuales)

    altas = derivados - presentes
    reactivados = {c for c in derivados & presentes if actuales[c] == FUERA_DE_ALCANCE}
    fuera = {c for c in presentes - derivados if actuales[c] != FUERA_DE_ALCANCE}

    return Reconciliacion(
        altas=tuple(sorted(altas)),
        fuera_de_alcance=tuple(sorted(fuera)),
        reactivados=tuple(sorted(reactivados)),
        sin_cambio=tuple(sorted((derivados & presentes) - reactivados)),
    )
