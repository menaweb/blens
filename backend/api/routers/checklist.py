"""Checklist de medidas (M4) e índices de cumplimiento (M6).

La madurez sale y entra siempre por `MeasureAssessment` (§15): es la única fuente, y la
que después alimenta el riesgo residual. Cambiar un nivel aquí encola el recálculo del
riesgo, que es lo que cierra el acoplamiento riesgo↔cumplimiento en un solo paso.
"""

from __future__ import annotations

from datetime import date

from apps.catalog.models import EnsMeasure
from apps.compliance.models import MeasureAssessment, System
from apps.compliance.services import (
    aplicabilidad_del_sistema,
    asegurar_valoraciones,
    puntuar_sistema,
    valoraciones_de,
)
from apps.risk.tasks import recalcular_riesgo
from apps.tenancy.permissions import require
from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.errors import HttpError

from api.auth import blens_auth
from engines.scoring_engine import ETIQUETA_POR_NIVEL, Indice, Resultado, ResultadoMedida

router = Router(auth=blens_auth)

NIVEL_MAXIMO = 5


class FilaOut(Schema):
    """Una fila del checklist: lo que el cliente declara y lo que eso vale."""

    code: str
    nombre: str
    marco: str
    familia: str
    aplica: bool
    motivo: str
    madurez: int | None
    objetivo: int
    delta: int | None
    semaforo: str
    madurez_pct: float
    cumplimiento_pct: float
    #: Alcanza el objetivo pero no hay evidencia validada que lo sostenga (§10bis).
    no_soportada: bool
    responsable: str
    responsable_id: int | None
    fecha_limite: date | None
    notas: str


class IndiceOut(Schema):
    clave: str
    medidas: int
    con_datos: int
    en_objetivo: int
    no_soportadas: int
    madurez: float
    cumplimiento: float
    madurez_media: float
    peor: str | None


class ChecklistOut(Schema):
    system_id: int
    sistema: str
    categoria: str
    #: Madurez mínima que exige su categoría (CCN-STIC-815).
    objetivo_categoria: int
    escala: dict[str, str]
    medidas: list[FilaOut]
    sistema_indice: IndiceOut
    por_marco: dict[str, IndiceOut]
    por_familia: dict[str, IndiceOut]
    #: Dónde se pierde más, de más caro a más barato.
    brechas: list[str]


def _indice_out(indice: Indice) -> IndiceOut:
    return IndiceOut(
        clave=indice.clave,
        medidas=indice.medidas,
        con_datos=indice.con_datos,
        en_objetivo=indice.en_objetivo,
        no_soportadas=indice.no_soportadas,
        madurez=float(indice.madurez),
        cumplimiento=float(indice.cumplimiento),
        madurez_media=float(indice.madurez_media),
        peor=indice.peor,
    )


def _fila_out(
    puntuada: ResultadoMedida,
    medida: EnsMeasure,
    valoracion: MeasureAssessment | None,
    motivo: str,
) -> FilaOut:
    responsable = valoracion.responsable if valoracion else None
    return FilaOut(
        code=puntuada.measure_id,
        nombre=medida.nombre,
        marco=puntuada.marco,
        familia=puntuada.familia,
        aplica=puntuada.aplica,
        motivo=motivo,
        madurez=puntuada.madurez,
        objetivo=puntuada.objetivo,
        delta=puntuada.delta,
        semaforo=puntuada.semaforo,
        madurez_pct=float(puntuada.madurez_pct),
        cumplimiento_pct=float(puntuada.cumplimiento_pct),
        no_soportada=puntuada.no_soportada,
        responsable=responsable.get_full_name() or responsable.username if responsable else "",
        responsable_id=responsable.pk if responsable else None,
        fecha_limite=valoracion.fecha_limite if valoracion else None,
        notas=valoracion.notas if valoracion else "",
    )


def _checklist_out(system: System, resultado: Resultado) -> ChecklistOut:
    medidas = {m.code: m for m in EnsMeasure.objects.filter(catalog_id=_catalogo_de(system))}
    valoraciones = valoraciones_de(system)
    motivos = aplicabilidad_del_sistema(system)
    return ChecklistOut(
        system_id=system.pk,
        sistema=system.nombre,
        categoria=system.categoria,
        objetivo_categoria=resultado.objetivo_categoria,
        escala={f"L{nivel}": texto for nivel, texto in ETIQUETA_POR_NIVEL.items()},
        # El motor devuelve las medidas por código, que es lo determinista; la pantalla
        # las enseña en el orden del Anexo II (org → op → mp), que es el que reconoce
        # cualquiera que haya leído la norma.
        medidas=[
            _fila_out(
                puntuada,
                medidas[puntuada.measure_id],
                valoraciones.get(puntuada.measure_id),
                motivos.get(puntuada.measure_id, ""),
            )
            for puntuada in sorted(resultado.medidas, key=lambda m: medidas[m.measure_id].orden)
        ],
        sistema_indice=_indice_out(resultado.sistema),
        por_marco={clave: _indice_out(i) for clave, i in resultado.por_marco.items()},
        por_familia={clave: _indice_out(i) for clave, i in resultado.por_familia.items()},
        brechas=[m.measure_id for m in resultado.brechas],
    )


def _catalogo_de(system: System) -> int:
    from apps.catalog.models import CatalogVersion

    version = CatalogVersion.current()
    if version is None:
        raise HttpError(409, "No hay ninguna versión del catálogo importada.")
    return version.pk


@router.get(
    "/systems/{system_id}/checklist", response=ChecklistOut, summary="Checklist de medidas (M4)"
)
def checklist(request, system_id: int):
    """Devuelve la tabla completa con sus índices ya calculados.

    Crea de paso las filas de madurez que falten: el cliente tiene que poder asignar
    responsable y fecha a una medida antes de haber declarado ningún nivel.
    """
    system = get_object_or_404(System, pk=system_id)
    require(request.user, "madurez.leer", system)
    if not system.categoria:
        raise HttpError(409, "El sistema no está categorizado todavía.")
    asegurar_valoraciones(system)
    return _checklist_out(system, puntuar_sistema(system))


class ValoracionIn(Schema):
    """Lo que se puede editar en línea. Lo que no se manda, no se toca."""

    maturity_level: int | None = None
    objetivo: int | None = None
    applies: bool | None = None
    responsable_id: int | None = None
    fecha_limite: date | None = None
    notas: str | None = None
    #: Para poder borrar el nivel o el objetivo, que `None` significa «no lo cambies».
    limpiar: list[str] | None = None


CAMPOS_LIMPIABLES = {"maturity_level", "objetivo", "responsable_id", "fecha_limite"}


@router.patch(
    "/systems/{system_id}/checklist/{code}",
    response=ChecklistOut,
    summary="Editar la madurez de una medida",
)
def patch_medida(request, system_id: int, code: str, datos: ValoracionIn):
    """Guarda el cambio y encola el recálculo del riesgo.

    Es el paso único del criterio de cierre de la fase: una madurez cambia y con ella
    cambian el índice de cumplimiento (que se devuelve aquí mismo, recalculado) y el
    riesgo residual (que se rehace en Celery, porque recorre el grafo entero).
    """
    system = get_object_or_404(System, pk=system_id)
    require(request.user, "madurez.editar", system)
    asegurar_valoraciones(system)
    fila = get_object_or_404(MeasureAssessment, system=system, measure__code=code)

    for campo in datos.limpiar or []:
        if campo not in CAMPOS_LIMPIABLES:
            raise HttpError(400, f"El campo {campo} no se puede vaciar.")
        setattr(fila, campo, None)

    for nivel in (datos.maturity_level, datos.objetivo):
        if nivel is not None and not 0 <= nivel <= NIVEL_MAXIMO:
            raise HttpError(400, "La madurez y el objetivo van de L0 a L5.")

    if datos.maturity_level is not None:
        fila.maturity_level = datos.maturity_level
    if datos.objetivo is not None:
        fila.objetivo = datos.objetivo
    if datos.applies is not None:
        fila.applies = datos.applies
    if datos.responsable_id is not None:
        fila.responsable_id = datos.responsable_id
    if datos.fecha_limite is not None:
        fila.fecha_limite = datos.fecha_limite
    if datos.notas is not None:
        fila.notas = datos.notas
    fila.save()

    recalcular_riesgo.delay(system.pk)
    return _checklist_out(system, puntuar_sistema(system))
