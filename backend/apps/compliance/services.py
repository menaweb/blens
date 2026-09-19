"""Categorización (M1) y generación de la Declaración de Aplicabilidad (M2).

Aquí no se decide nada por cuenta propia: la aplicabilidad la da
`engines.ens_applicability` y la categoría sale del Anexo I. Este módulo solo persiste.
"""

from __future__ import annotations

import glob
import uuid
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

import yaml
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import CatalogVersion, EnsMeasure
from apps.catalog.services import build_catalog
from apps.compliance.models import (
    DeclaracionAplicabilidad,
    DimensionValuation,
    InformeCategorizacion,
    MeasureApplied,
    MeasureAssessment,
    categoria_de,
)
from engines.ens_applicability import Perfil, Resultado, aplicabilidad
from engines.scoring_engine import Medida as ScoringMedida
from engines.scoring_engine import Resultado as ScoringResultado
from engines.scoring_engine import puntuar

RAIZ = Path(__file__).resolve().parents[3]
SEED_EVIDENCIAS = RAIZ / "db" / "seed" / "blens"

#: Cuánto vive una categorización anónima antes de borrarse (datos de quien aún no es cliente).
DIAS_CADUCIDAD_ANONIMA = 30


# --- Categorización (M1) --------------------------------------------------------


@lru_cache(maxsize=1)
def _plantillas_por_medida() -> dict[str, list[dict]]:
    """Plantillas de evidencia del seed, agrupadas por medida.

    Se usa solo para dar las cifras del resultado de la categorización. Es una
    **estimación**: las plantillas con `applies_if` dependen del perfilado (M11), que en
    este punto todavía no se ha hecho.
    """
    salida: dict[str, list[dict]] = {}
    for ruta in glob.glob(str(SEED_EVIDENCIAS / "evidence_templates.*.yaml")):
        with open(ruta, encoding="utf-8") as fichero:
            for plantilla in yaml.safe_load(fichero)["templates"]:
                salida.setdefault(plantilla["measure"], []).append(plantilla)
    return salida


def resumen(resultado: Resultado) -> dict:
    """Las cifras y el desglose que enseña la pantalla de resultado."""
    plantillas = _plantillas_por_medida()
    aplicables = resultado.measure_ids

    evidencias = 0
    documentos = 0
    for measure_id in aplicables:
        for plantilla in plantillas.get(measure_id, []):
            if not plantilla.get("obligatoria"):
                continue
            if plantilla.get("generable"):
                documentos += 1
            else:
                evidencias += 1

    por_familia: dict[str, int] = {}
    for medida in resultado.aplicables:
        por_familia[medida.familia] = por_familia.get(medida.familia, 0) + 1

    return {
        "medidas": len(aplicables),
        "refuerzos_obligatorios": len(resultado.refuerzos_obligatorios),
        "selecciones_pendientes": len(resultado.selecciones_pendientes),
        "evidencias_estimadas": evidencias,
        "documentos_generables": documentos,
        "por_familia": dict(sorted(por_familia.items())),
        "por_marco": {
            marco: sum(1 for m in resultado.aplicables if m.marco == marco)
            for marco in ("org", "op", "mp")
        },
        "dimensiones_que_marcan": _dimensiones_que_marcan(resultado.perfil),
    }


def _dimensiones_que_marcan(perfil: Perfil) -> list[str]:
    """Qué dimensiones son las que fijan la categoría ('por autenticidad y trazabilidad')."""
    from engines.oscal_io.models import ORDEN_NIVEL

    mayor = max((ORDEN_NIVEL[n] for n in perfil.niveles.values()), default=0)
    if mayor == 0:
        return []
    return [dim for dim, nivel in perfil.niveles.items() if ORDEN_NIVEL[nivel] == mayor]


def categorizar(
    niveles: dict[str, str], version: CatalogVersion | None = None
) -> tuple[Perfil, Resultado]:
    """Aplica el Anexo I y deriva la aplicabilidad. No guarda nada."""
    version = version or CatalogVersion.current()
    if version is None:
        raise RuntimeError("No hay ninguna versión del catálogo importada.")
    perfil = Perfil(categoria=categoria_de(niveles), niveles=dict(niveles))
    return perfil, aplicabilidad(build_catalog(version), perfil)


def crear_informe(
    niveles: dict[str, str],
    *,
    organizacion: str = "",
    alcance: str = "",
    tenant=None,
    system=None,
) -> InformeCategorizacion:
    """Guarda el resultado para poder generar el PDF (M1 funciona sin cuenta)."""
    perfil, resultado = categorizar(niveles)
    return InformeCategorizacion.objects.create(
        token=uuid.uuid4(),
        tenant=tenant,
        system=system,
        organizacion=organizacion,
        alcance=alcance,
        niveles=dict(niveles),
        categoria=perfil.categoria,
        resumen=resumen(resultado),
        expira_en=None if tenant else timezone.now() + timedelta(days=DIAS_CADUCIDAD_ANONIMA),
    )


@transaction.atomic
def guardar_valoracion(system, niveles: dict[str, str]) -> None:
    """Persiste el nivel de cada dimensión y actualiza la categoría del sistema."""
    for dim, nivel in niveles.items():
        DimensionValuation.objects.update_or_create(
            system=system, dim=dim, defaults={"nivel": nivel}
        )
    system.categoria = categoria_de(niveles)
    system.save(update_fields=["categoria"])


# --- Declaración de Aplicabilidad (M2) ------------------------------------------


def niveles_de(system) -> dict[str, str]:
    return {v.dim: v.nivel for v in system.valoraciones.all()}


@transaction.atomic
def generar_dda(
    system, usuario=None, version: CatalogVersion | None = None
) -> DeclaracionAplicabilidad:
    """Crea una versión nueva de la DdA a partir de la categorización del sistema.

    Cada generación es una versión nueva: no se pisa la anterior, que puede estar
    aprobada y formar parte de un expediente.
    """
    version = version or CatalogVersion.current()
    niveles = niveles_de(system)
    if not niveles:
        raise ValueError("El sistema no está categorizado: no hay niveles por dimensión.")

    perfil, resultado = categorizar(niveles, version)
    ultima = system.declaraciones.first()

    dda = DeclaracionAplicabilidad.objects.create(
        tenant=system.tenant,
        system=system,
        version=(ultima.version + 1) if ultima else 1,
        catalog=version,
        categoria=perfil.categoria,
        niveles=niveles,
        creada_por=usuario,
    )

    medidas = {m.code: m for m in EnsMeasure.objects.filter(catalog=version)}
    aplicables = {m.measure_id: m for m in resultado.aplicables}

    filas = []
    for code, medida in medidas.items():
        aplicable = aplicables.get(code)
        if aplicable is None:
            motivo = dict(resultado.no_aplicables).get(code, "")
            filas.append(
                MeasureApplied(
                    dda=dda,
                    measure=medida,
                    aplica=False,
                    motivo=motivo,
                    justificacion=f"No exigida por el catálogo: {motivo}",
                )
            )
            continue
        filas.append(
            MeasureApplied(
                dda=dda,
                measure=medida,
                aplica=True,
                motivo=aplicable.motivo,
                refuerzos_obligatorios=list(aplicable.refuerzos_obligatorios),
                refuerzos_opcionales=list(aplicable.refuerzos_opcionales),
                selecciones={s.param_id: "" for s in aplicable.selecciones},
            )
        )
    MeasureApplied.objects.bulk_create(filas)
    return dda


# --- Madurez y scoring (M4 / M6) ------------------------------------------------


def aplicabilidad_del_sistema(system) -> dict[str, str]:
    """`{code: motivo}` de las medidas que aplican a este sistema.

    Manda la **última DdA** si la hay: es la decisión formal del cliente, con sus no
    aplicables justificadas. Sin DdA se deriva de la categorización, para que el
    checklist funcione desde el primer minuto sin obligar a generar una declaración.
    """
    ultima = system.declaraciones.first()
    if ultima is not None:
        return {
            fila.measure.code: fila.motivo
            for fila in ultima.medidas.select_related("measure")
            if fila.aplica
        }
    niveles = niveles_de(system)
    if not niveles:
        return {}
    _, resultado = categorizar(niveles)
    return {m.measure_id: m.motivo for m in resultado.aplicables}


def valoraciones_de(system) -> dict[str, MeasureAssessment]:
    return {
        fila.measure.code: fila
        for fila in MeasureAssessment.objects.filter(system=system).select_related("measure")
    }


@transaction.atomic
def asegurar_valoraciones(system) -> int:
    """Crea la fila de madurez que falte para cada medida aplicable, sin valorar.

    Sin valorar no es L0: es «nadie la ha mirado». El checklist necesita la fila para
    poder asignar responsable y fecha antes de que nadie declare un nivel.
    """
    aplicables = aplicabilidad_del_sistema(system)
    existentes = set(valoraciones_de(system))
    version = CatalogVersion.current()
    faltan = [
        MeasureAssessment(tenant=system.tenant, system=system, measure=medida)
        for medida in EnsMeasure.objects.filter(catalog=version)
        if medida.code in aplicables and medida.code not in existentes
    ]
    MeasureAssessment.objects.bulk_create(faltan)
    return len(faltan)


def medidas_para_scoring(system) -> list[ScoringMedida]:
    """Traduce la base de datos a la entrada del motor puro (§15: el motor no ve Django)."""
    aplicables = aplicabilidad_del_sistema(system)
    valoraciones = valoraciones_de(system)
    version = CatalogVersion.current()
    salida = []
    for medida in EnsMeasure.objects.filter(catalog=version):
        valoracion = valoraciones.get(medida.code)
        aplica = medida.code in aplicables
        if valoracion is not None and not valoracion.applies:
            aplica = False  # el checklist permite excluirla; la justificación va en la DdA
        salida.append(
            ScoringMedida(
                measure_id=medida.code,
                marco=medida.marco,
                familia=medida.familia,
                madurez=valoracion.maturity_level if valoracion else None,
                objetivo=valoracion.objetivo if valoracion else None,
                aplica=aplica,
                soportada=valoracion.madurez_soportada if valoracion else True,
            )
        )
    return salida


def puntuar_sistema(system) -> ScoringResultado:
    """Índices de madurez y cumplimiento del sistema. No guarda nada: se recalcula."""
    return puntuar(medidas_para_scoring(system), system.categoria)
