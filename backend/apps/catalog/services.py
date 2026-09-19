"""Puente entre las tablas del catálogo y los motores puros.

Los motores no conocen Django (§15): reciben el `Catalog` de `engines.oscal_io`. Aquí se
reconstruye desde la base de datos, para que en ejecución mande lo importado y no el
fichero del disco.
"""

from __future__ import annotations

from functools import lru_cache

from apps.catalog.models import CatalogVersion
from engines.ens_applicability import Perfil, Resultado, aplicabilidad
from engines.oscal_io.models import (
    Aplicabilidad,
    Catalog,
    Measure,
    Refuerzo,
    RequirementItem,
    SelectionParam,
)


def _aplicabilidad(fila) -> Aplicabilidad:
    return Aplicabilidad(
        aplicacion_por=fila.aplicacion_por or None,
        categorias=frozenset(fila.categorias or []),
        niveles=frozenset(fila.niveles or []),
        dimensiones=frozenset(fila.dimensiones or []),
    )


def _items(filas, parent_id=None) -> tuple[RequirementItem, ...]:
    return tuple(
        RequirementItem(
            id=fila.code,
            label=fila.label,
            prose=fila.prose,
            orden=fila.orden,
            children=_items(filas, fila.pk),
        )
        for fila in filas
        if fila.parent_id == parent_id
    )


def build_catalog(version: CatalogVersion) -> Catalog:
    """Reconstruye el catálogo en memoria a partir de una `CatalogVersion`."""
    items = list(version.items.all())
    por_medida: dict[int, list] = {}
    por_refuerzo: dict[int, list] = {}
    for item in items:
        destino = por_refuerzo if item.refuerzo_id else por_medida
        clave = item.refuerzo_id or item.measure_id
        destino.setdefault(clave, []).append(item)

    measures = []
    for medida in version.measures.prefetch_related("refuerzos", "params"):
        measures.append(
            Measure(
                id=medida.code,
                marco=medida.marco,
                familia=medida.familia,
                titulo=medida.nombre,
                aplicabilidad=_aplicabilidad(medida),
                overview=medida.overview,
                requisitos=_items(por_medida.get(medida.pk, [])),
                refuerzos=tuple(
                    Refuerzo(
                        id=refuerzo.code,
                        measure_id=medida.code,
                        titulo=refuerzo.titulo,
                        aplicabilidad=_aplicabilidad(refuerzo),
                        requisitos=_items(por_refuerzo.get(refuerzo.pk, [])),
                    )
                    for refuerzo in medida.refuerzos.all()
                ),
                params=tuple(
                    SelectionParam(
                        id=param.code,
                        measure_id=medida.code,
                        label=param.label,
                        usage=param.usage,
                        choices=tuple(param.choices),
                        nivel=param.nivel or None,
                        categoria=param.categoria or None,
                    )
                    for param in medida.params.all()
                ),
            )
        )

    return Catalog(
        titulo=version.code,
        version=version.source_version,
        oscal_version=version.oscal_version,
        last_modified=version.source_last_modified,
        remarks=version.remarks,
        source_url=version.source_url,
        measures=tuple(measures),
    )


@lru_cache(maxsize=4)
def _cacheado(version_pk: int, sha256: str) -> Catalog:
    # El sha256 forma parte de la clave: si se reimporta el catálogo, la caché se renueva
    # sola sin tener que acordarse de vaciarla.
    return build_catalog(CatalogVersion.objects.get(pk=version_pk))


def catalogo_vigente() -> Catalog | None:
    version = CatalogVersion.current()
    return _cacheado(version.pk, version.source_sha256) if version else None


def aplicabilidad_de(perfil: Perfil, version: CatalogVersion | None = None) -> Resultado:
    """Deriva la aplicabilidad para un perfil con el catálogo vigente (o el que se pase)."""
    catalogo = build_catalog(version) if version else catalogo_vigente()
    if catalogo is None:
        raise RuntimeError("No hay ninguna versión del catálogo importada.")
    return aplicabilidad(catalogo, perfil)
