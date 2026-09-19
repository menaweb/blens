"""Sistemas, categorización guardada y Declaración de Aplicabilidad (M2).

Todo lo de aquí pasa por `can()` (§15): ni una comprobación de rol suelta. Autenticación
por sesión de Django mientras Cognito no esté cableado (§5, D1).
"""

from __future__ import annotations

import json
from typing import Literal

from apps.compliance.models import DeclaracionAplicabilidad, MeasureApplied, System
from apps.compliance.services import generar_dda, guardar_valoracion, niveles_de
from apps.compliance.tasks import render_dda
from apps.tenancy.models import Membership
from apps.tenancy.permissions import can, require
from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.errors import HttpError
from ninja.security import django_auth

from engines.oscal_io.export import DecisionMedida, dda_to_oscal_profile

router = Router(auth=django_auth)

NivelIn = Literal["NA", "BAJO", "MEDIO", "ALTO"]


def _tenant_de(request):
    membresia = Membership.objects.filter(user=request.user).first()
    if membresia is None or not membresia.vigente:
        raise HttpError(403, "El usuario no pertenece a ninguna organización activa.")
    return membresia.tenant


class SystemIn(Schema):
    nombre: str
    descripcion: str = ""


class SystemOut(Schema):
    id: int
    nombre: str
    descripcion: str
    categoria: str
    niveles: dict[str, str]


def _system_out(system: System) -> SystemOut:
    return SystemOut(
        id=system.pk,
        nombre=system.nombre,
        descripcion=system.descripcion,
        categoria=system.categoria,
        niveles=niveles_de(system),
    )


@router.get("/systems", response=list[SystemOut], summary="Sistemas de la organización")
def systems(request):
    tenant = _tenant_de(request)
    return [
        _system_out(s)
        for s in System.objects.filter(tenant=tenant)
        if can(request.user, "categorizacion.leer", s)
    ]


@router.post("/systems", response=SystemOut, summary="Dar de alta un sistema")
def create_system(request, datos: SystemIn):
    tenant = _tenant_de(request)
    require(request.user, "categorizacion.editar", tenant=tenant)
    system = System.objects.create(
        tenant=tenant, nombre=datos.nombre, descripcion=datos.descripcion
    )
    return _system_out(system)


class ValoracionIn(Schema):
    C: NivelIn = "NA"
    I: NivelIn = "NA"  # noqa: E741
    T: NivelIn = "NA"
    A: NivelIn = "NA"
    D: NivelIn = "NA"


@router.put(
    "/systems/{system_id}/valuation", response=SystemOut, summary="Guardar la categorización"
)
def set_valuation(request, system_id: int, datos: ValoracionIn):
    system = get_object_or_404(System, pk=system_id)
    require(request.user, "categorizacion.editar", system)
    guardar_valoracion(
        system, {"C": datos.C, "I": datos.I, "T": datos.T, "A": datos.A, "D": datos.D}
    )
    system.refresh_from_db()
    return _system_out(system)


# --- Declaración de Aplicabilidad ----------------------------------------------


class MedidaOut(Schema):
    code: str
    nombre: str
    marco: str
    familia: str
    aplica: bool
    motivo: str
    justificacion: str
    compensatoria: str
    refuerzos_obligatorios: list[str]
    refuerzos_opcionales: list[str]
    selecciones: dict[str, str]


class DdaOut(Schema):
    id: int
    version: int
    estado: str
    categoria: str
    niveles: dict[str, str]
    catalogo: str
    madurez_minima: int
    problemas: list[str]
    medidas: list[MedidaOut]


def _dda_out(dda: DeclaracionAplicabilidad) -> DdaOut:
    return DdaOut(
        id=dda.pk,
        version=dda.version,
        estado=dda.estado,
        categoria=dda.categoria,
        niveles=dda.niveles,
        catalogo=dda.catalog.code,
        madurez_minima=dda.madurez_minima,
        problemas=dda.problemas(),
        medidas=[
            MedidaOut(
                code=m.measure.code,
                nombre=m.measure.nombre,
                marco=m.measure.marco,
                familia=m.measure.familia,
                aplica=m.aplica,
                motivo=m.motivo,
                justificacion=m.justificacion,
                compensatoria=m.compensatoria,
                refuerzos_obligatorios=m.refuerzos_obligatorios,
                refuerzos_opcionales=m.refuerzos_opcionales,
                selecciones=m.selecciones,
            )
            for m in dda.medidas.select_related("measure")
        ],
    )


@router.post("/systems/{system_id}/dda", response=DdaOut, summary="Generar una versión de la DdA")
def create_dda(request, system_id: int):
    system = get_object_or_404(System, pk=system_id)
    require(request.user, "dda.editar", system)
    try:
        dda = generar_dda(system, usuario=request.user)
    except ValueError as error:
        raise HttpError(400, str(error)) from error
    return _dda_out(dda)


@router.get("/dda/{dda_id}", response=DdaOut, summary="Detalle de una DdA")
def get_dda(request, dda_id: int):
    dda = get_object_or_404(DeclaracionAplicabilidad, pk=dda_id)
    require(request.user, "dda.leer", dda.system)
    return _dda_out(dda)


class DecisionIn(Schema):
    aplica: bool | None = None
    justificacion: str | None = None
    compensatoria: str | None = None
    #: {param_id: refuerzo elegido}
    selecciones: dict[str, str] | None = None


@router.patch(
    "/dda/{dda_id}/measures/{code}", response=MedidaOut, summary="Editar una medida de la DdA"
)
def patch_measure(request, dda_id: int, code: str, datos: DecisionIn):
    dda = get_object_or_404(DeclaracionAplicabilidad, pk=dda_id)
    require(request.user, "dda.editar", dda.system)
    if dda.estado == "APROBADA":
        raise HttpError(409, "Una DdA aprobada no se edita: genera una versión nueva.")

    fila = get_object_or_404(MeasureApplied, dda=dda, measure__code=code)
    if datos.aplica is not None:
        fila.aplica = datos.aplica
    if datos.justificacion is not None:
        fila.justificacion = datos.justificacion
    if datos.compensatoria is not None:
        fila.compensatoria = datos.compensatoria
    if datos.selecciones is not None:
        validas = {opcion for param in fila.measure.params.all() for opcion in param.choices}
        for param_id, elegido in datos.selecciones.items():
            if elegido and elegido not in validas:
                raise HttpError(400, f"{elegido} no es una opción válida de {param_id}.")
            fila.selecciones[param_id] = elegido
    fila.save()
    return (
        _dda_out(dda)
        .medidas[0]
        .__class__(
            code=fila.measure.code,
            nombre=fila.measure.nombre,
            marco=fila.measure.marco,
            familia=fila.measure.familia,
            aplica=fila.aplica,
            motivo=fila.motivo,
            justificacion=fila.justificacion,
            compensatoria=fila.compensatoria,
            refuerzos_obligatorios=fila.refuerzos_obligatorios,
            refuerzos_opcionales=fila.refuerzos_opcionales,
            selecciones=fila.selecciones,
        )
    )


@router.post("/dda/{dda_id}/approve", response=DdaOut, summary="Aprobar la DdA")
def approve_dda(request, dda_id: int):
    """Solo el RSEG, y solo si no quedan selecciones sin resolver ni no-aplicables sin justificar."""
    dda = get_object_or_404(DeclaracionAplicabilidad, pk=dda_id)
    require(request.user, "dda.aprobar", dda.system)
    try:
        dda.aprobar(request.user)
    except ValidationError as error:
        # 409 con la lista de lo que falta: la UI los enseña uno a uno, no como un texto.
        return JsonResponse({"problemas": error.messages}, status=409)
    return _dda_out(dda)


@router.get("/dda/{dda_id}/oscal", summary="Exportar la DdA en OSCAL (profile)")
def export_oscal(request, dda_id: int):
    dda = get_object_or_404(DeclaracionAplicabilidad, pk=dda_id)
    require(request.user, "dda.leer", dda.system)

    perfil = dda_to_oscal_profile(
        organizacion=dda.tenant.nombre if dda.tenant else "",
        sistema=dda.system.nombre,
        version=dda.version,
        categoria=dda.categoria,
        niveles=dda.niveles,
        catalogo_href=dda.catalog.source_url,
        catalogo_version=dda.catalog.code,
        fecha=(dda.aprobada_en or dda.creada_en).isoformat(),
        aprobador=str(dda.aprobador) if dda.aprobador else "",
        decisiones=[
            DecisionMedida(
                measure_id=m.measure.code,
                aplica=m.aplica,
                motivo=m.motivo,
                justificacion=m.justificacion,
                compensatoria=m.compensatoria,
                refuerzos=tuple(m.refuerzos_obligatorios),
                selecciones=m.selecciones,
            )
            for m in dda.medidas.select_related("measure")
        ],
    )
    respuesta = HttpResponse(
        json.dumps(perfil, ensure_ascii=False, indent=2), content_type="application/json"
    )
    respuesta["Content-Disposition"] = f'attachment; filename="dda-v{dda.version}-oscal.json"'
    return respuesta


@router.post("/dda/{dda_id}/pdf", summary="Encolar el PDF de la DdA")
def queue_pdf(request, dda_id: int):
    dda = get_object_or_404(DeclaracionAplicabilidad, pk=dda_id)
    require(request.user, "dda.leer", dda.system)
    tarea = render_dda.delay(dda.pk)
    return {"tarea": tarea.id, "estado": "ENCOLADO"}
