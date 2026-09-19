"""Lectura del Catalog OSCAL 1.1.3 del Anexo II (AEAD, EUPL-1.2).

El JSON oficial **no se edita nunca** (`db/seed/oscal/`): se lee y se normaliza aquí.

Sobre la validación: no se valida contra el JSON Schema oficial de OSCAL, que exigiría
traerse el esquema y una dependencia más. En su lugar se comprueba lo que de verdad puede
romper a BLENS —versión de OSCAL, estructura de grupos, ids únicos, props conocidas,
refuerzos colgando de su medida, items con label— y se falla con un informe de todo lo
que esté mal, no solo del primer fallo.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import (
    CATEGORIAS,
    DIMENSIONES,
    NIVELES,
    POR_CATEGORIA,
    POR_NIVEL_DIMENSION,
    Aplicabilidad,
    Catalog,
    Measure,
    Refuerzo,
    RequirementItem,
    SelectionParam,
)

NS = "urn:es:ens"
CLASE_REFUERZO = "ens-refuerzo"
OSCAL_SOPORTADO = "1.1"


class OscalValidationError(ValueError):
    """El fichero no es el catálogo que BLENS espera. Lleva el informe completo."""

    def __init__(self, errores: list[str]):
        self.errores = errores
        super().__init__("Catálogo OSCAL inválido:\n" + "\n".join(f"  - {e}" for e in errores))


def _props(nodo: dict, nombre: str, ns: str | None = NS) -> list[str]:
    return [
        p["value"] for p in nodo.get("props", []) if p.get("name") == nombre and p.get("ns") == ns
    ]


def _prop(nodo: dict, nombre: str, ns: str | None = NS) -> str | None:
    valores = _props(nodo, nombre, ns)
    return valores[0] if valores else None


def _aplicabilidad(nodo: dict, errores: list[str]) -> Aplicabilidad:
    aplicacion_por = _prop(nodo, "aplicacion-por")
    if aplicacion_por is not None and aplicacion_por not in (POR_CATEGORIA, POR_NIVEL_DIMENSION):
        errores.append(f"{nodo.get('id')}: aplicacion-por desconocida {aplicacion_por!r}")

    categorias = set(_props(nodo, "categoria"))
    niveles = set(_props(nodo, "nivel"))
    dimensiones = set()
    for nombre in _props(nodo, "dimension"):
        if nombre not in DIMENSIONES:
            errores.append(f"{nodo.get('id')}: dimensión desconocida {nombre!r}")
        else:
            dimensiones.add(DIMENSIONES[nombre])

    for valor in categorias - set(CATEGORIAS):
        errores.append(f"{nodo.get('id')}: categoría desconocida {valor!r}")
    for valor in niveles - set(NIVELES):
        errores.append(f"{nodo.get('id')}: nivel desconocido {valor!r}")

    return Aplicabilidad(
        aplicacion_por=aplicacion_por,
        categorias=frozenset(categorias),
        niveles=frozenset(niveles),
        dimensiones=frozenset(dimensiones),
    )


def _items(partes: list[dict], errores: list[str], dueño: str) -> tuple[RequirementItem, ...]:
    salida = []
    for orden, parte in enumerate(partes or [], start=1):
        if parte.get("name") != "item":
            continue
        label = _prop(parte, "label", ns=None)
        children = _items(parte.get("parts", []), errores, dueño)
        # Los items que agrupan a otros (p. ej. mp.s.1) no llevan numeración propia; los
        # que son hoja sí, y es esa numeración la que cita el auditor.
        if not label and not children:
            errores.append(f"{dueño}: item {parte.get('id')} sin label")
        salida.append(
            RequirementItem(
                id=parte.get("id") or f"{dueño}.item.{orden}",
                label=label or "",
                prose=parte.get("prose", ""),
                orden=orden,
                children=children,
            )
        )
    return tuple(salida)


def _requisitos(control: dict, errores: list[str]) -> tuple[RequirementItem, ...]:
    for parte in control.get("parts", []):
        if parte.get("name") == "requisitos":
            return _items(parte.get("parts", []), errores, control["id"])
    return ()


def _prosa_anidada(parte: dict) -> list[str]:
    salida = [parte.get("prose", "")] if parte.get("prose") else []
    for hija in parte.get("parts", []) or []:
        salida += _prosa_anidada(hija)
    return salida


def _texto(control: dict, nombre: str) -> str:
    """Texto de una parte, incluida la de sus items anidados.

    mp.eq.4 es el único caso: su `overview` cuelga el texto de cinco items. Son
    aclaraciones, no requisitos, así que se aplanan aquí y **no** entran como
    `RequirementItem` (por eso el catálogo tiene 467 items y 462 requisitos).
    """
    for parte in control.get("parts", []):
        if parte.get("name") == nombre:
            return "\n".join(_prosa_anidada(parte))
    return ""


def _params(control: dict, errores: list[str]) -> tuple[SelectionParam, ...]:
    salida = []
    for param in control.get("params", []):
        if _prop(param, "tipo-param") != "seleccion-refuerzo":
            continue
        seleccion = param.get("select") or {}
        choices = tuple(seleccion.get("choice", []))
        if not choices:
            errores.append(f"{param.get('id')}: selección de refuerzo sin opciones")
        salida.append(
            SelectionParam(
                id=param["id"],
                measure_id=control["id"],
                label=param.get("label", ""),
                usage=param.get("usage", ""),
                choices=choices,
                how_many=seleccion.get("how-many", "one"),
                nivel=_prop(param, "nivel"),
                categoria=_prop(param, "categoria"),
            )
        )
    return tuple(salida)


def _refuerzos(control: dict, errores: list[str]) -> tuple[Refuerzo, ...]:
    salida = []
    for hijo in control.get("controls", []):
        if hijo.get("class") != CLASE_REFUERZO:
            errores.append(f"{hijo.get('id')}: control anidado que no es un refuerzo")
            continue
        if not hijo["id"].startswith(f"{control['id']}."):
            errores.append(f"{hijo['id']}: no cuelga del id de su medida {control['id']}")
        salida.append(
            Refuerzo(
                id=hijo["id"],
                measure_id=control["id"],
                titulo=hijo.get("title", ""),
                aplicabilidad=_aplicabilidad(hijo, errores),
                requisitos=_requisitos(hijo, errores),
            )
        )
    return tuple(salida)


def parse_catalog(data: dict) -> Catalog:
    """Normaliza el JSON OSCAL. Levanta `OscalValidationError` con TODOS los problemas."""
    errores: list[str] = []
    catalogo = data.get("catalog")
    if catalogo is None:
        raise OscalValidationError(["el JSON no tiene raíz 'catalog'"])

    meta = catalogo.get("metadata", {})
    oscal_version = meta.get("oscal-version", "")
    if not oscal_version.startswith(OSCAL_SOPORTADO):
        errores.append(
            f"versión OSCAL no soportada: {oscal_version!r} (se espera {OSCAL_SOPORTADO}.x)"
        )

    measures: list[Measure] = []
    for marco in catalogo.get("groups", []):
        if marco.get("class") != "family":
            errores.append(f"{marco.get('id')}: grupo raíz que no es 'family'")
        familias = marco.get("groups") or [marco]  # org no tiene subfamilias
        for familia in familias:
            for control in familia.get("controls", []):
                if control.get("class") == CLASE_REFUERZO:
                    errores.append(f"{control['id']}: refuerzo suelto fuera de su medida")
                    continue
                measures.append(
                    Measure(
                        id=control["id"],
                        marco=marco["id"],
                        familia=familia["id"],
                        titulo=control.get("title", ""),
                        aplicabilidad=_aplicabilidad(control, errores),
                        overview=_texto(control, "overview"),
                        requisitos=_requisitos(control, errores),
                        refuerzos=_refuerzos(control, errores),
                        params=_params(control, errores),
                    )
                )

    vistos: set[str] = set()
    for medida in measures:
        for identificador in [medida.id, *(r.id for r in medida.refuerzos)]:
            if identificador in vistos:
                errores.append(f"id repetido en el catálogo: {identificador}")
            vistos.add(identificador)

    if not measures:
        errores.append("el catálogo no contiene ninguna medida")
    if errores:
        raise OscalValidationError(errores)

    enlaces = {enlace.get("rel"): enlace.get("href") for enlace in meta.get("links", [])}
    return Catalog(
        titulo=meta.get("title", ""),
        version=meta.get("version", ""),
        oscal_version=oscal_version,
        last_modified=meta.get("last-modified", ""),
        remarks=meta.get("remarks", ""),
        source_url=enlaces.get("source", ""),
        measures=tuple(measures),
    )


def load_catalog(path: str | Path) -> tuple[Catalog, str]:
    """Lee el fichero y devuelve `(catálogo, sha256)`. El sha256 va en `CatalogVersion`."""
    ruta = Path(path)
    crudo = ruta.read_bytes()
    return parse_catalog(json.loads(crudo.decode("utf-8"))), hashlib.sha256(crudo).hexdigest()
