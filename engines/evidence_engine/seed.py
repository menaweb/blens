"""Del YAML del seed a los objetos del motor. Conversión pura: aquí no se abre un fichero.

Quien lee el disco es quien tenga disco: el comando `seed_blens` (que además escribe en la
base de datos) y los tests. Así el mismo diccionario vale para los dos y no hay dos
interpretaciones del seed conviviendo —que es justo como se cuelan las diferencias entre
lo que valida la CI y lo que acaba viendo el cliente.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .engine import Campo, Opcion, Plantilla, Pregunta

__all__ = [
    "bloques_desde",
    "plantilla_desde",
    "plantillas_desde",
    "pregunta_desde",
    "preguntas_desde",
]


def pregunta_desde(datos: Mapping[str, Any]) -> Pregunta:
    return Pregunta(
        code=datos["code"],
        bloque=datos.get("bloque", ""),
        orden=int(datos.get("orden", 0)),
        tipo=datos.get("tipo", "SINGLE"),
        texto=datos.get("texto", ""),
        show_if=datos.get("show_if"),
        opciones=tuple(
            Opcion(code=o["code"], label=o.get("label", ""), emits=dict(o.get("emits") or {}))
            for o in datos.get("opciones") or []
        ),
        campos=tuple(
            Campo(code=c["code"], label=c.get("label", "")) for c in datos.get("campos") or []
        ),
        emits=dict(datos.get("emits") or {}),
        funcion=datos.get("funcion", ""),
        minutos_estimados=int(datos.get("minutos_estimados", 1)),
    )


def preguntas_desde(documento: Mapping[str, Any]) -> tuple[Pregunta, ...]:
    return tuple(pregunta_desde(p) for p in documento.get("questions") or [])


def bloques_desde(documento: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    """Los bloques del cuestionario, que son la unidad de delegación por rol (M11)."""
    return tuple(dict(b) for b in documento.get("bloques") or [])


def plantilla_desde(datos: Mapping[str, Any]) -> Plantilla:
    return Plantilla(
        code=datos["code"],
        measure=datos["measure"],
        titulo=datos.get("titulo", ""),
        tipo=datos.get("tipo", ""),
        refuerzo=datos.get("refuerzo") or "",
        option_group=datos.get("option_group") or "",
        preferencia=int(datos.get("preferencia") or 0),
        obligatoria=bool(datos.get("obligatoria", True)),
        applies_if=datos.get("applies_if"),
        vigencia_dias=datos.get("vigencia_dias"),
        carpeta_paquete=datos.get("carpeta_paquete", ""),
        generable=bool(datos.get("generable", False)),
    )


def plantillas_desde(documento: Mapping[str, Any]) -> tuple[Plantilla, ...]:
    return tuple(plantilla_desde(t) for t in documento.get("templates") or [])
