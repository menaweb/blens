"""Del catálogo en base de datos a los objetos del motor.

`engines.evidence_engine` no sabe que existe Django (§6), así que alguien tiene que
traducir. Ese alguien es este módulo, y solo este: si mañana el motor cambia de forma, se
toca aquí y no en cada vista.
"""

from __future__ import annotations

from apps.catalog.models import CatalogVersion, EvidenceTemplate, ProfileQuestion
from engines.evidence_engine import Campo, Opcion, Plantilla, Pregunta


def preguntas_del_catalogo(catalog: CatalogVersion) -> tuple[Pregunta, ...]:
    filas = (
        ProfileQuestion.objects.filter(catalog=catalog)
        .select_related("bloque")
        .prefetch_related("opciones")
    )
    return tuple(pregunta_de(fila) for fila in filas)


def plantillas_del_catalogo(catalog: CatalogVersion) -> tuple[Plantilla, ...]:
    filas = EvidenceTemplate.objects.filter(catalog=catalog).select_related("measure", "refuerzo")
    return tuple(plantilla_de(fila) for fila in filas)


def pregunta_de(fila: ProfileQuestion) -> Pregunta:
    return Pregunta(
        code=fila.code,
        bloque=fila.bloque.code if fila.bloque_id else "",
        orden=fila.orden,
        tipo=fila.tipo,
        texto=fila.texto,
        show_if=fila.show_if,
        opciones=tuple(
            Opcion(code=o.code, label=o.label, emits=o.emits or {}) for o in fila.opciones.all()
        ),
        campos=tuple(Campo(code=c["code"], label=c.get("label", "")) for c in fila.campos or []),
        emits=fila.emits or {},
        funcion=fila.funcion,
        minutos_estimados=fila.minutos_estimados,
    )


def plantilla_de(fila: EvidenceTemplate) -> Plantilla:
    return Plantilla(
        code=fila.code,
        measure=fila.measure.code,
        titulo=fila.titulo,
        tipo=fila.tipo,
        refuerzo=fila.refuerzo.code if fila.refuerzo_id else "",
        option_group=fila.option_group,
        preferencia=fila.preferencia,
        obligatoria=fila.obligatoria,
        applies_if=fila.applies_if,
        vigencia_dias=fila.vigencia_dias,
        carpeta_paquete=fila.carpeta_paquete,
        generable=fila.generable,
    )
