"""Importa el catálogo OSCAL oficial del Anexo II.

Tres cosas que este comando garantiza (§15):

1. **Idempotente.** Reimportar el mismo fichero no duplica nada: se reconoce por su
   sha256 y se reescribe la misma versión.
2. **Validado.** El parseo falla con un informe completo si el fichero no es el catálogo
   que BLENS espera (`engines.oscal_io`).
3. **Sin referencias huérfanas.** Si una versión nueva borra o renombra un id que la capa
   propia cita (checks, plantillas de evidencia, mapa MAGERIT), **el import falla** y dice
   exactamente qué fichero lo cita. Sin esto, una actualización de la norma rompería el
   seed en silencio.
"""

from __future__ import annotations

import glob
import os
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.models import (
    CatalogVersion,
    EnsMeasure,
    EnsRefuerzo,
    EnsRequirementItem,
    EnsSelectionParam,
)
from engines.oscal_io import Catalog, load_catalog
from engines.oscal_io.parser import OscalValidationError

RAIZ = Path(__file__).resolve().parents[5]
SEED_PROPIO = RAIZ / "db" / "seed" / "blens"

#: Claves de los YAML del seed que citan un id del catálogo.
CLAVES_REFERENCIA = ("measure", "refuerzo", "item", "measure_id")


def _referencias_de_la_capa_propia(base: Path = SEED_PROPIO) -> dict[str, set[str]]:
    """`{id citado: {ficheros que lo citan}}`, recorriendo todo el seed propio."""
    referencias: dict[str, set[str]] = {}

    def visitar(nodo, fichero: str) -> None:
        if isinstance(nodo, dict):
            for clave, valor in nodo.items():
                if clave in CLAVES_REFERENCIA and isinstance(valor, str):
                    referencias.setdefault(valor, set()).add(fichero)
                else:
                    visitar(valor, fichero)
        elif isinstance(nodo, list):
            for elemento in nodo:
                visitar(elemento, fichero)

    for ruta in glob.glob(str(base / "**" / "*.yaml"), recursive=True):
        with open(ruta, encoding="utf-8") as fichero:
            visitar(yaml.safe_load(fichero), os.path.relpath(ruta, base))
    return referencias


class Command(BaseCommand):
    help = "Importa el catálogo ENS (Anexo II) desde el JSON OSCAL oficial."

    def add_arguments(self, parser) -> None:
        parser.add_argument("path", help="Ruta del JSON OSCAL (db/seed/oscal/…)")
        parser.add_argument(
            "--code", help="Código de la versión; por defecto se deriva del fichero"
        )
        parser.add_argument(
            "--no-activate",
            action="store_true",
            help="No marcar esta versión como vigente.",
        )
        parser.add_argument(
            "--skip-orphan-check",
            action="store_true",
            help="Importar aunque la capa propia quede con referencias huérfanas (no recomendado).",
        )

    def handle(self, *args, **opciones) -> None:
        ruta = Path(opciones["path"])
        if not ruta.exists():
            raise CommandError(f"No existe el fichero {ruta}")

        try:
            catalogo, sha256 = load_catalog(ruta)
        except OscalValidationError as error:
            raise CommandError(str(error)) from error

        code = opciones["code"] or f"ENS-2022-OSCAL-{catalogo.version}"

        if not opciones["skip_orphan_check"]:
            self._comprobar_referencias(catalogo)

        with transaction.atomic():
            version, creada = self._guardar(catalogo, code, sha256, ruta)
            if not opciones["no_activate"]:
                CatalogVersion.objects.exclude(pk=version.pk).update(is_current=False)
                CatalogVersion.objects.filter(pk=version.pk).update(is_current=True)

        verbo = "Creada" if creada else "Reescrita"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verbo} la versión {version.code}: "
                f"{version.measures.count()} medidas, "
                f"{EnsRefuerzo.objects.filter(measure__catalog=version).count()} refuerzos, "
                f"{version.items.count()} requisitos."
            )
        )

    # --- pasos -----------------------------------------------------------------

    def _comprobar_referencias(self, catalogo: Catalog) -> None:
        if not SEED_PROPIO.exists():
            return
        conocidos = catalogo.ids()
        huerfanas = {
            identificador: ficheros
            for identificador, ficheros in _referencias_de_la_capa_propia().items()
            if identificador not in conocidos
        }
        if huerfanas:
            informe = "\n".join(
                f"  - {identificador} (citado en {', '.join(sorted(ficheros))})"
                for identificador, ficheros in sorted(huerfanas.items())
            )
            raise CommandError(
                "Esta versión del catálogo dejaría huérfanas referencias de la capa propia:\n"
                f"{informe}\n"
                "Actualiza el seed antes de importar, o usa --skip-orphan-check si sabes lo que haces."
            )

    def _guardar(
        self, catalogo: Catalog, code: str, sha256: str, ruta: Path
    ) -> tuple[CatalogVersion, bool]:
        version, creada = CatalogVersion.objects.update_or_create(
            code=code,
            defaults={
                "oscal_version": catalogo.oscal_version,
                "source_version": catalogo.version,
                "source_last_modified": catalogo.last_modified,
                "source_url": catalogo.source_url,
                "source_sha256": sha256,
                "source_path": str(ruta),
                "remarks": catalogo.remarks,
            },
        )
        # Reimportar reescribe: más simple y seguro que ir casando diferencias, y el
        # catálogo es pequeño. Los datos de tenant apuntan al code, que no cambia.
        version.measures.all().delete()
        version.items.all().delete()

        for orden, medida in enumerate(catalogo.measures, start=1):
            fila = EnsMeasure.objects.create(
                catalog=version,
                code=medida.id,
                marco=medida.marco,
                familia=medida.familia,
                nombre=medida.titulo,
                overview=medida.overview,
                aplicacion_por=medida.aplicabilidad.aplicacion_por or "",
                categorias=sorted(medida.aplicabilidad.categorias),
                niveles=sorted(medida.aplicabilidad.niveles),
                dimensiones=sorted(medida.aplicabilidad.dimensiones),
                orden=orden,
            )
            self._guardar_items(version, fila, None, medida.requisitos)

            for indice, refuerzo in enumerate(medida.refuerzos, start=1):
                fila_refuerzo = EnsRefuerzo.objects.create(
                    measure=fila,
                    code=refuerzo.id,
                    titulo=refuerzo.titulo,
                    aplicacion_por=refuerzo.aplicabilidad.aplicacion_por or "",
                    categorias=sorted(refuerzo.aplicabilidad.categorias),
                    niveles=sorted(refuerzo.aplicabilidad.niveles),
                    dimensiones=sorted(refuerzo.aplicabilidad.dimensiones),
                    opcional=refuerzo.opcional,
                    orden=indice,
                )
                self._guardar_items(version, fila, fila_refuerzo, refuerzo.requisitos)

            for param in medida.params:
                EnsSelectionParam.objects.create(
                    measure=fila,
                    code=param.id,
                    label=param.label,
                    usage=param.usage,
                    categoria=param.categoria or "",
                    nivel=param.nivel or "",
                    choices=list(param.choices),
                )
        return version, creada

    def _guardar_items(self, version, medida, refuerzo, items, parent=None) -> None:
        for item in items:
            fila = EnsRequirementItem.objects.create(
                catalog=version,
                code=item.id,
                label=item.label,
                measure=medida,
                refuerzo=refuerzo,
                parent=parent,
                prose=item.prose,
                orden=item.orden,
            )
            self._guardar_items(version, medida, refuerzo, item.children, parent=fila)
