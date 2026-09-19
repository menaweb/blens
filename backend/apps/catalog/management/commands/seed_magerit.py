"""Carga la capa MAGERIT del catálogo: tipos de activo, amenazas, eficacias y salvaguardas.

Es la parte del seed propio que consume `engines.risk_engine`. Como el resto del
catálogo, es **dato versionado** (`db/seed/blens/magerit/*.yaml`) y cuelga de la
`CatalogVersion` vigente: no hay una sola medida ni un solo peso escrito en el código.

Idempotente: se vuelve a ejecutar tantas veces como haga falta y deja lo mismo. **Hay que
volver a ejecutarlo después de cada `import_ens_oscal`**, porque reimportar el catálogo
reescribe las medidas y el mapa cuelga de ellas.

Valida antes de escribir, y no escribe nada si algo falla: un peso fuera de rango o una
medida que ya no existe en la norma detienen la carga entera con el detalle.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.models import (
    Aspecto,
    CatalogVersion,
    EnsMeasure,
    MageritAssetType,
    MageritThreat,
    MageritThreatDefault,
    MaturityEffectiveness,
    MeasureThreatMap,
)

RAIZ = Path(__file__).resolve().parents[5]
SEED = RAIZ / "db" / "seed" / "blens" / "magerit"

#: Tope de §15: ninguna medida sola puede anular una amenaza.
PESO_MAXIMO = Decimal("0.7")
DIMENSIONES = {"C", "I", "T", "A", "D"}


def _leer(nombre: str) -> dict:
    ruta = SEED / nombre
    if not ruta.exists():
        raise CommandError(f"Falta el fichero del seed: {ruta}")
    with open(ruta, encoding="utf-8") as fichero:
        return yaml.safe_load(fichero)


class Command(BaseCommand):
    help = "Carga el seed MAGERIT (tipos de activo, amenazas y mapa medida-amenaza)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--catalog",
            help="Código de la CatalogVersion a la que colgarlo; por defecto, la vigente.",
        )
        parser.add_argument(
            "--layer-version",
            default="",
            help="Versión de la capa propia que se anota en la CatalogVersion.",
        )

    def handle(self, *args, **opciones) -> None:
        version = (
            CatalogVersion.objects.filter(code=opciones["catalog"]).first()
            if opciones["catalog"]
            else CatalogVersion.current()
        )
        if version is None:
            raise CommandError(
                "No hay ninguna versión del catálogo vigente. Ejecuta antes import_ens_oscal."
            )

        tipos = _leer("asset_types.yaml")
        amenazas = _leer("threats.yaml")
        mapa = _leer("measure_threat_map.yaml")
        eficacias = _leer("maturity_effectiveness.yaml")

        medidas = {m.code: m for m in EnsMeasure.objects.filter(catalog=version)}
        self._validar(tipos, amenazas, mapa, eficacias, medidas)

        with transaction.atomic():
            self._cargar_eficacias(eficacias)
            self._cargar_tipos(version, tipos)
            self._cargar_amenazas(version, amenazas)
            pares = self._cargar_mapa(version, mapa, medidas)
            if opciones["layer_version"]:
                CatalogVersion.objects.filter(pk=version.pk).update(
                    blens_layer_version=opciones["layer_version"]
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed MAGERIT cargado en {version.code}: "
                f"{MageritAssetType.objects.filter(catalog=version).count()} tipos de activo, "
                f"{MageritThreat.objects.filter(catalog=version).count()} amenazas, "
                f"{pares} salvaguardas."
            )
        )

    # --- validación -------------------------------------------------------------

    def _validar(self, tipos, amenazas, mapa, eficacias, medidas) -> None:
        """Las mismas reglas que `validate_seed.py` comprueba en CI, aquí contra la BD."""
        errores: list[str] = []

        codigos_tipo = set()
        for tipo in tipos["asset_types"]:
            codigos_tipo.add(tipo["code"])
            codigos_tipo.update(sub["code"] for sub in tipo.get("subtipos", []))

        codigos_amenaza = set()
        for amenaza in amenazas["threats"]:
            codigos_amenaza.add(amenaza["code"])
            for dim in amenaza["dims"]:
                if dim not in DIMENSIONES:
                    errores.append(f"{amenaza['code']}: dimensión desconocida {dim!r}")
            for tipo in amenaza.get("aplica_a", []):
                if tipo not in codigos_tipo:
                    errores.append(f"{amenaza['code']}: tipo de activo desconocido {tipo!r}")

        niveles = {fila["level"] for fila in eficacias["levels"]}
        if niveles != set(range(6)):
            errores.append(f"La tabla de eficacia tiene que cubrir L0-L5; cubre {sorted(niveles)}")

        vistos: set[tuple] = set()
        sin_salvaguarda = codigos_amenaza - set(mapa["map"])
        for codigo in sorted(sin_salvaguarda):
            errores.append(f"amenaza sin ninguna salvaguarda: {codigo}")

        for codigo, entradas in mapa["map"].items():
            if codigo not in codigos_amenaza:
                errores.append(f"el mapa cita una amenaza que no existe: {codigo}")
            for entrada in entradas:
                if entrada["measure"] not in medidas:
                    errores.append(
                        f"{codigo}: la medida {entrada['measure']} no está en el catálogo importado"
                    )
                if entrada["aspect"] not in Aspecto.values:
                    errores.append(f"{codigo}: aspecto desconocido {entrada['aspect']!r}")
                peso = Decimal(str(entrada["weight"]))
                if not (Decimal("0") < peso <= PESO_MAXIMO):
                    errores.append(
                        f"{codigo}/{entrada['measure']}: peso {peso} fuera de (0, {PESO_MAXIMO}]"
                    )
                clave = (codigo, entrada["measure"], entrada.get("dim") or "", entrada["aspect"])
                if clave in vistos:
                    errores.append(f"par duplicado en el mapa: {clave}")
                vistos.add(clave)

        # Toda medida del ENS tiene que aparecer al menos una vez como salvaguarda (§15):
        # si alguna no frena nada, o falta en el mapa o sobra en la norma.
        citadas = {e["measure"] for entradas in mapa["map"].values() for e in entradas}
        for code in sorted(set(medidas) - citadas):
            errores.append(f"medida sin salvaguarda en el mapa MAGERIT: {code}")

        if errores:
            raise CommandError("El seed MAGERIT no es válido:\n  - " + "\n  - ".join(errores))

    # --- carga -------------------------------------------------------------------

    def _cargar_eficacias(self, eficacias) -> None:
        for fila in eficacias["levels"]:
            MaturityEffectiveness.objects.update_or_create(
                level=fila["level"],
                defaults={
                    "label": fila["label"],
                    "effectiveness": Decimal(str(fila["effectiveness"])),
                },
            )

    def _cargar_tipos(self, version, tipos) -> None:
        MageritAssetType.objects.filter(catalog=version).delete()
        orden = 0
        for tipo in tipos["asset_types"]:
            orden += 1
            padre = MageritAssetType.objects.create(
                catalog=version,
                code=tipo["code"],
                name=tipo["name"],
                is_terminal=bool(tipo.get("is_terminal")),
                ayuda=tipo.get("ayuda", ""),
                orden=orden,
            )
            for subtipo in tipo.get("subtipos", []):
                orden += 1
                MageritAssetType.objects.create(
                    catalog=version,
                    code=subtipo["code"],
                    name=subtipo["name"],
                    is_terminal=padre.is_terminal,
                    parent=padre,
                    orden=orden,
                )

    def _cargar_amenazas(self, version, amenazas) -> None:
        MageritThreat.objects.filter(catalog=version).delete()
        for orden, amenaza in enumerate(amenazas["threats"], start=1):
            fila = MageritThreat.objects.create(
                catalog=version,
                code=amenaza["code"],
                name=amenaza["name"],
                category=amenaza["category"],
                dims=list(amenaza["dims"]),
                aplica_a=list(amenaza.get("aplica_a", [])),
                orden=orden,
            )
            frecuencia = Decimal(str(amenaza["default_frequency"]))
            for dim, degradacion in amenaza["default_degradation"].items():
                MageritThreatDefault.objects.create(
                    threat=fila,
                    dim=dim,
                    default_degradation=Decimal(str(degradacion)),
                    default_frequency=frecuencia,
                )

    def _cargar_mapa(self, version, mapa, medidas) -> int:
        MeasureThreatMap.objects.filter(catalog=version).delete()
        amenazas = {t.code: t for t in MageritThreat.objects.filter(catalog=version)}
        filas = [
            MeasureThreatMap(
                catalog=version,
                measure=medidas[entrada["measure"]],
                threat=amenazas[codigo],
                dim=entrada.get("dim") or "",
                aspect=entrada["aspect"],
                weight=Decimal(str(entrada["weight"])),
            )
            for codigo, entradas in mapa["map"].items()
            for entrada in entradas
        ]
        MeasureThreatMap.objects.bulk_create(filas)
        return len(filas)
