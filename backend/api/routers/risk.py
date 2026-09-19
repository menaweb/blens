"""Análisis de riesgos MAGERIT (M7): activos, dependencias, amenazas y tratamiento.

Ningún cálculo vive aquí. Las vistas leen, escriben y encolan; el número lo da
`engines.risk_engine` a través de `apps.risk.services`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from apps.catalog.models import MageritAssetType, MageritThreat
from apps.compliance.models import System
from apps.risk.models import Asset, AssetDependency, AssetValuation, RiskTreatment, ThreatInstance
from apps.risk.services import amenazas_por_defecto, simular_instancia
from apps.risk.tasks import recalcular_riesgo
from apps.tenancy.permissions import require
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError
from ninja.security import django_auth

router = Router(auth=django_auth)

DIMENSIONES = ("C", "I", "T", "A", "D")


# --- Activos y dependencias ---------------------------------------------------------


class ActivoOut(Schema):
    id: int
    nombre: str
    descripcion: str
    tipo: str
    tipo_nombre: str
    terminal: bool
    valores: dict[str, float]


class ActivoIn(Schema):
    nombre: str
    tipo: str  # código de MageritAssetType
    descripcion: str = ""
    valores: dict[str, float] = {}
    #: Instanciar de una vez las amenazas que el catálogo propone para ese tipo.
    proponer_amenazas: bool = True


def _activo_out(activo: Asset) -> ActivoOut:
    return ActivoOut(
        id=activo.pk,
        nombre=activo.nombre,
        descripcion=activo.descripcion,
        tipo=activo.asset_type.code,
        tipo_nombre=activo.asset_type.name,
        terminal=activo.asset_type.is_terminal,
        valores={v.dim: float(v.own_value) for v in activo.valoraciones.all()},
    )


@router.get(
    "/systems/{system_id}/assets", response=list[ActivoOut], summary="Inventario de activos"
)
def activos(request, system_id: int):
    system = get_object_or_404(System, pk=system_id)
    require(request.user, "riesgo.leer", system)
    return [
        _activo_out(a)
        for a in Asset.objects.filter(system=system)
        .select_related("asset_type")
        .prefetch_related("valoraciones")
    ]


@router.post("/systems/{system_id}/assets", response=ActivoOut, summary="Dar de alta un activo")
def crear_activo(request, system_id: int, datos: ActivoIn):
    system = get_object_or_404(System, pk=system_id)
    require(request.user, "riesgo.editar", system)
    tipo = get_object_or_404(MageritAssetType, code=datos.tipo, catalog__is_current=True)
    try:
        activo = Asset.objects.create(
            tenant=system.tenant,
            system=system,
            asset_type=tipo,
            nombre=datos.nombre,
            descripcion=datos.descripcion,
        )
    except IntegrityError as error:
        raise HttpError(
            409, f"Ya hay un activo llamado «{datos.nombre}» en este sistema."
        ) from error

    _guardar_valores(activo, datos.valores)
    if datos.proponer_amenazas:
        amenazas_por_defecto(activo)
    return _activo_out(activo)


class ValoresIn(Schema):
    valores: dict[str, float]


@router.put(
    "/assets/{asset_id}/valuation", response=ActivoOut, summary="Valorar un activo (0 a 10)"
)
def valorar_activo(request, asset_id: int, datos: ValoresIn):
    activo = get_object_or_404(Asset, pk=asset_id)
    require(request.user, "riesgo.editar", activo.system)
    _guardar_valores(activo, datos.valores)
    return _activo_out(activo)


def _guardar_valores(activo: Asset, valores: dict[str, float]) -> None:
    for dim, valor in valores.items():
        if dim not in DIMENSIONES:
            raise HttpError(400, f"Dimensión desconocida: {dim}.")
        if not 0 <= valor <= 10:
            raise HttpError(400, "Los activos se valoran de 0 a 10.")
        AssetValuation.objects.update_or_create(
            asset=activo, dim=dim, defaults={"own_value": Decimal(str(valor))}
        )


class DependenciaOut(Schema):
    id: int
    parent: int
    child: int
    degree: float


class DependenciaIn(Schema):
    parent: int
    child: int
    degree: float = 1.0


@router.get(
    "/systems/{system_id}/dependencies",
    response=list[DependenciaOut],
    summary="Grafo de dependencias",
)
def dependencias(request, system_id: int):
    system = get_object_or_404(System, pk=system_id)
    require(request.user, "riesgo.leer", system)
    return [
        DependenciaOut(id=d.pk, parent=d.parent_id, child=d.child_id, degree=float(d.degree))
        for d in AssetDependency.objects.filter(parent__system=system)
    ]


@router.post(
    "/systems/{system_id}/dependencies",
    response=DependenciaOut,
    summary="Declarar que un activo depende de otro",
)
def crear_dependencia(request, system_id: int, datos: DependenciaIn):
    """`parent` depende de `child`: el valor desciende del primero al segundo.

    El ciclo no se rechaza aquí sino al recalcular, donde se puede nombrar entero. Lo
    que sí se rechaza de entrada es lo que no tiene arreglo: depender de uno mismo o de
    un activo de otro sistema.
    """
    system = get_object_or_404(System, pk=system_id)
    require(request.user, "riesgo.editar", system)
    padre = get_object_or_404(Asset, pk=datos.parent, system=system)
    hijo = get_object_or_404(Asset, pk=datos.child, system=system)
    if not 0 < datos.degree <= 1:
        raise HttpError(400, "El grado de dependencia va de 0 (exclusive) a 1.")
    dependencia = AssetDependency(parent=padre, child=hijo, degree=Decimal(str(datos.degree)))
    try:
        dependencia.full_clean()
    except ValidationError as error:
        raise HttpError(400, " ".join(error.messages)) from error
    dependencia.save()
    return DependenciaOut(
        id=dependencia.pk,
        parent=padre.pk,
        child=hijo.pk,
        degree=float(dependencia.degree),
    )


@router.delete("/dependencies/{dependency_id}", summary="Quitar una dependencia")
def borrar_dependencia(request, dependency_id: int):
    dependencia = get_object_or_404(AssetDependency, pk=dependency_id)
    require(request.user, "riesgo.editar", dependencia.parent.system)
    dependencia.delete()
    return {"borrada": dependency_id}


# --- Amenazas, riesgo y tratamiento --------------------------------------------------


class SalvaguardaOut(Schema):
    measure: str
    aspect: str
    weight: float
    nivel: int
    eficacia: float
    soportada: bool


class RiesgoOut(Schema):
    id: int
    asset_id: int
    activo: str
    threat: str
    amenaza: str
    dim: str
    frequency: float
    degradation: float
    valor_acumulado: float | None
    riesgo_intrinseco: float | None
    riesgo_residual: float | None
    calculado_en: str | None
    salvaguardas: list[SalvaguardaOut]
    decision: str
    riesgo_objetivo: float | None


def _riesgo_out(instancia: ThreatInstance) -> RiesgoOut:
    resultado = getattr(instancia, "resultado", None)
    tratamiento = getattr(instancia, "tratamiento", None)
    return RiesgoOut(
        id=instancia.pk,
        asset_id=instancia.asset_id,
        activo=instancia.asset.nombre,
        threat=instancia.threat.code,
        amenaza=instancia.threat.name,
        dim=instancia.dim,
        frequency=float(instancia.frequency),
        degradation=float(instancia.degradation),
        valor_acumulado=float(resultado.accumulated_value) if resultado else None,
        riesgo_intrinseco=float(resultado.intrinsic_risk) if resultado else None,
        riesgo_residual=float(resultado.residual_risk) if resultado else None,
        calculado_en=resultado.computed_at.isoformat() if resultado else None,
        salvaguardas=[SalvaguardaOut(**s) for s in (resultado.salvaguardas if resultado else [])],
        decision=tratamiento.decision if tratamiento else "",
        riesgo_objetivo=(
            float(tratamiento.target_risk) if tratamiento and tratamiento.target_risk else None
        ),
    )


@router.get(
    "/systems/{system_id}/risks",
    response=list[RiesgoOut],
    summary="Riesgos del sistema, de mayor a menor residual",
)
def riesgos(request, system_id: int):
    system = get_object_or_404(System, pk=system_id)
    require(request.user, "riesgo.leer", system)
    instancias = (
        ThreatInstance.objects.filter(asset__system=system)
        .select_related("asset", "threat", "resultado", "tratamiento")
        .order_by("-resultado__residual_risk", "asset__nombre", "threat__orden")
    )
    return [_riesgo_out(i) for i in instancias]


class AmenazaIn(Schema):
    threat: str  # código MAGERIT
    dim: str
    frequency: float
    degradation: float
    notas: str = ""


@router.post("/assets/{asset_id}/threats", response=RiesgoOut, summary="Añadir o ajustar amenaza")
def amenaza(request, asset_id: int, datos: AmenazaIn):
    activo = get_object_or_404(Asset, pk=asset_id)
    require(request.user, "riesgo.editar", activo.system)
    if datos.dim not in DIMENSIONES:
        raise HttpError(400, f"Dimensión desconocida: {datos.dim}.")
    if not 0 <= datos.degradation <= 1:
        raise HttpError(400, "La degradación va de 0 a 1.")
    if datos.frequency < 0:
        raise HttpError(400, "La frecuencia no puede ser negativa.")
    amenaza_catalogo = get_object_or_404(
        MageritThreat, code=datos.threat, catalog=activo.asset_type.catalog
    )
    instancia, _ = ThreatInstance.objects.update_or_create(
        asset=activo,
        threat=amenaza_catalogo,
        dim=datos.dim,
        defaults={
            "tenant": activo.tenant,
            "frequency": Decimal(str(datos.frequency)),
            "degradation": Decimal(str(datos.degradation)),
            "notas": datos.notas,
        },
    )
    return _riesgo_out(instancia)


@router.post(
    "/systems/{system_id}/risks/recompute", summary="Recalcular el riesgo (en segundo plano)"
)
def recalcular(request, system_id: int):
    """Encola el recálculo. Recorre el grafo entero: no va en la petición (§15)."""
    system = get_object_or_404(System, pk=system_id)
    require(request.user, "riesgo.editar", system)
    tarea = recalcular_riesgo.delay(system.pk)
    return {"tarea": tarea.id, "estado": "ENCOLADO"}


class SimulacionIn(Schema):
    objetivo: float


@router.post("/risks/{risk_id}/simulate", summary="¿Qué habría que subir para llegar ahí?")
def simular(request, risk_id: int, datos: SimulacionIn):
    instancia = get_object_or_404(ThreatInstance, pk=risk_id)
    require(request.user, "riesgo.leer", instancia.asset.system)
    try:
        simulacion = simular_instancia(instancia, Decimal(str(datos.objetivo)))
    except ValueError as error:
        raise HttpError(409, str(error)) from error
    return {
        "alcanzable": simulacion.alcanzable,
        "riesgo_inicial": float(simulacion.riesgo_inicial),
        "riesgo_final": float(simulacion.riesgo_final),
        "subidas": [
            {
                "measure": s.measure_id,
                "nivel_actual": s.nivel_actual,
                "nivel_propuesto": s.nivel_propuesto,
            }
            for s in simulacion.subidas
        ],
    }


class TratamientoIn(Schema):
    decision: str
    target_risk: float | None = None
    owner_id: int | None = None
    due_date: date | None = None
    notes: str = ""


@router.put("/risks/{risk_id}/treatment", response=RiesgoOut, summary="Decidir qué se hace")
def tratamiento(request, risk_id: int, datos: TratamientoIn):
    """Aceptar un riesgo es una decisión de dirección, no un valor por defecto.

    Por eso `riesgo.aceptar` es una acción propia en la matriz y queda registrado quién
    lo acepta y cuándo: es lo primero que mira un auditor ante un riesgo alto asumido.
    """
    from apps.risk.models import Decision

    instancia = get_object_or_404(ThreatInstance, pk=risk_id)
    if datos.decision and datos.decision not in Decision.values:
        raise HttpError(400, f"Decisión desconocida: {datos.decision}.")
    accion = "riesgo.aceptar" if datos.decision == Decision.ACEPTAR else "riesgo.editar"
    require(request.user, accion, instancia.asset.system)

    tratamiento, _ = RiskTreatment.objects.update_or_create(
        threat_instance=instancia,
        defaults={
            "tenant": instancia.tenant,
            "decision": datos.decision,
            "target_risk": Decimal(str(datos.target_risk)) if datos.target_risk else None,
            "owner_id": datos.owner_id,
            "due_date": datos.due_date,
            "notes": datos.notes,
        },
    )
    if datos.decision == Decision.ACEPTAR:
        tratamiento.aceptado_por = request.user
        tratamiento.aceptado_en = timezone.now()
        tratamiento.save(update_fields=["aceptado_por", "aceptado_en"])
    instancia.refresh_from_db()
    return _riesgo_out(instancia)
