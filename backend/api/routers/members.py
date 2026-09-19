"""Usuarios y roles de una organización (M0), y el registro de actividad propio.

Todo lo de aquí pasa por `can()` (§15). Las dos reglas que el sistema impone y que no
son de Cognito sino de BLENS: una organización **nunca** se queda sin propietario, y
restablecer el segundo factor de otra persona deja rastro de quién lo hizo.
"""

from __future__ import annotations

from apps.tenancy.models import AuditLog, Invitation, Membership, Role
from apps.tenancy.permissions import require
from apps.tenancy.services import (
    ReglaDeNegocio,
    cambiar_rol,
    invitar,
    restablecer_mfa,
    revocar,
    transferir_propiedad,
)
from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.errors import HttpError

from api.auth import blens_auth, email_normalizado

router = Router(auth=blens_auth)


def _ip(request):
    adelantado = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (adelantado.split(",")[0].strip() or request.META.get("REMOTE_ADDR")) or None


def _agente(request) -> str:
    return request.META.get("HTTP_USER_AGENT", "")[:300]


def tenant_de(request):
    """Organización en la que actúa quien llama.

    Hoy una persona trabaja con una sola organización; el selector de cliente llega con
    el modo consultora (M10), que depende del aislamiento de tenant.
    """
    membresia = Membership.objects.filter(user=request.user).select_related("tenant").first()
    if membresia is None or not membresia.vigente:
        raise HttpError(403, "El usuario no pertenece a ninguna organización activa.")
    return membresia.tenant


class MiembroOut(Schema):
    id: int
    email: str
    nombre: str = ""
    role: str
    role_nombre: str
    estado: str
    expires_at: str = ""
    caducada: bool = False
    mfa_activado: bool = False
    systems: list[int] = []
    bloques: list[str] = []


def _miembro_out(m: Membership) -> MiembroOut:
    identidad = getattr(m.user, "identidad", None)
    return MiembroOut(
        id=m.pk,
        email=m.user.username,
        nombre=getattr(identidad, "nombre", "") or m.user.first_name,
        role=m.role,
        role_nombre=m.get_role_display(),
        estado=m.estado,
        expires_at=m.expires_at.isoformat() if m.expires_at else "",
        caducada=m.caducada,
        mfa_activado=getattr(identidad, "mfa_activado", False),
        systems=[s.pk for s in m.systems.all()],
        bloques=m.bloques,
    )


@router.get("/members", response=list[MiembroOut], summary="Miembros de la organización")
def members(request):
    tenant = tenant_de(request)
    require(request.user, "usuarios.leer", tenant=tenant)
    return [
        _miembro_out(m)
        for m in Membership.objects.filter(tenant=tenant)
        .select_related("user", "user__identidad")
        .prefetch_related("systems")
        .order_by("role", "id")
    ]


class InvitacionIn(Schema):
    email: str
    role: str
    systems: list[int] = []
    bloques: list[str] = []
    #: Días que durará la membresía. Obligatorio de hecho para auditor y consultor: si no
    #: se dice nada, se aplica el valor por defecto en lugar de dejarla sin caducidad.
    membership_dias: int | None = None


class InvitacionEmitidaOut(Schema):
    id: int
    email: str
    role: str
    caduca: str
    #: Enlace que hay que hacer llegar. Mientras el correo de SES no esté montado, se
    #: devuelve aquí para poder pasarlo a mano.
    enlace: str


@router.post(
    "/members/invitations",
    response={201: InvitacionEmitidaOut},
    summary="Invitar a alguien",
)
def invite(request, datos: InvitacionIn):
    tenant = tenant_de(request)
    if datos.role not in Role.values:
        raise HttpError(400, "Ese rol no existe.")
    # El RSEG puede dar acceso a un auditor sin poder gestionar al resto de usuarios.
    accion = "auditor.invitar" if datos.role == Role.AUDITOR else "usuarios.gestionar"
    require(request.user, accion, tenant=tenant)
    try:
        invitacion, token = invitar(
            tenant=tenant,
            email=email_normalizado(datos.email),
            role=datos.role,
            actor=request.user,
            systems=datos.systems,
            bloques=datos.bloques,
            membership_dias=datos.membership_dias,
            ip=_ip(request),
            user_agent=_agente(request),
        )
    except ReglaDeNegocio as exc:
        raise HttpError(409, str(exc)) from exc
    return 201, InvitacionEmitidaOut(
        id=invitacion.pk,
        email=invitacion.email,
        role=invitacion.role,
        caduca=invitacion.expires_at.isoformat(),
        enlace=f"/invitacion/{token}",
    )


class InvitacionPendienteOut(Schema):
    id: int
    email: str
    role: str
    role_nombre: str
    caduca: str


@router.get(
    "/members/invitations",
    response=list[InvitacionPendienteOut],
    summary="Invitaciones pendientes",
)
def invitations(request):
    tenant = tenant_de(request)
    require(request.user, "usuarios.leer", tenant=tenant)
    return [
        InvitacionPendienteOut(
            id=i.pk,
            email=i.email,
            role=i.role,
            role_nombre=i.get_role_display(),
            caduca=i.expires_at.isoformat(),
        )
        for i in Invitation.objects.filter(tenant=tenant, used_at__isnull=True).order_by("-id")
        if i.vigente
    ]


@router.delete(
    "/members/invitations/{invitacion_id}", response={204: None}, summary="Revocar la invitación"
)
def invitation_revoke(request, invitacion_id: int):
    tenant = tenant_de(request)
    require(request.user, "usuarios.gestionar", tenant=tenant)
    invitacion = get_object_or_404(Invitation, pk=invitacion_id, tenant=tenant)
    invitacion.delete()
    AuditLog.append(
        accion="miembro.invitacion_revocada",
        tenant=tenant,
        user=request.user,
        datos={"email": invitacion.email},
        ip=_ip(request),
        user_agent=_agente(request),
    )
    return 204, None


class CambioRolIn(Schema):
    role: str
    dias: int | None = None


@router.patch("/members/{membresia_id}", response=MiembroOut, summary="Cambiar el rol")
def member_update(request, membresia_id: int, datos: CambioRolIn):
    tenant = tenant_de(request)
    require(request.user, "usuarios.gestionar", tenant=tenant)
    membresia = get_object_or_404(Membership, pk=membresia_id, tenant=tenant)
    if datos.role not in Role.values:
        raise HttpError(400, "Ese rol no existe.")
    try:
        cambiar_rol(
            membresia=membresia,
            role=datos.role,
            actor=request.user,
            dias=datos.dias,
            ip=_ip(request),
            user_agent=_agente(request),
        )
    except ReglaDeNegocio as exc:
        raise HttpError(409, str(exc)) from exc
    return _miembro_out(membresia)


@router.post("/members/{membresia_id}/revoke", response=MiembroOut, summary="Revocar el acceso")
def member_revoke(request, membresia_id: int):
    tenant = tenant_de(request)
    require(request.user, "usuarios.gestionar", tenant=tenant)
    membresia = get_object_or_404(Membership, pk=membresia_id, tenant=tenant)
    try:
        revocar(
            membresia=membresia,
            actor=request.user,
            ip=_ip(request),
            user_agent=_agente(request),
        )
    except ReglaDeNegocio as exc:
        raise HttpError(409, str(exc)) from exc
    return _miembro_out(membresia)


@router.post(
    "/members/{membresia_id}/transfer-ownership",
    response=MiembroOut,
    summary="Transferir la propiedad",
)
def member_transfer(request, membresia_id: int):
    tenant = tenant_de(request)
    require(request.user, "usuarios.gestionar", tenant=tenant)
    destino = get_object_or_404(Membership, pk=membresia_id, tenant=tenant)
    try:
        transferir_propiedad(
            tenant=tenant,
            destino=destino,
            actor=request.user,
            ip=_ip(request),
            user_agent=_agente(request),
        )
    except ReglaDeNegocio as exc:
        raise HttpError(409, str(exc)) from exc
    return _miembro_out(destino)


class ReiniciarMfaOut(Schema):
    ok: bool = True
    mensaje: str


@router.post(
    "/members/{membresia_id}/reset-mfa",
    response=ReiniciarMfaOut,
    summary="Restablecer el segundo factor",
)
def member_reset_mfa(request, membresia_id: int):
    """Para quien ha perdido el móvil. Cognito no da códigos de recuperación (D1)."""
    tenant = tenant_de(request)
    require(request.user, "usuarios.gestionar", tenant=tenant)
    membresia = get_object_or_404(Membership, pk=membresia_id, tenant=tenant)
    if not hasattr(membresia.user, "identidad"):
        raise HttpError(409, "Esa persona no tiene identidad en el proveedor.")
    restablecer_mfa(
        membresia=membresia, actor=request.user, ip=_ip(request), user_agent=_agente(request)
    )
    return ReiniciarMfaOut(
        mensaje=(
            "Segundo factor restablecido. La próxima vez que entre, se le pedirá volver "
            "a configurarlo."
        )
    )


class ActividadOut(Schema):
    fecha: str
    accion: str
    objeto: str = ""
    datos: dict = {}


@router.get("/me/activity", response=list[ActividadOut], summary="Mi actividad")
def my_activity(request, limite: int = 50):
    """Lo que ha hecho quien llama. El registro encadenado, útil para su dueño y no solo
    para el auditor (`docs/roles_y_permisos.md` §5)."""
    entradas = AuditLog.objects.filter(user=request.user).order_by("-id")[: min(limite, 200)]
    return [
        ActividadOut(
            fecha=e.created_at.isoformat(),
            accion=e.accion,
            objeto=f"{e.objeto_tipo} {e.objeto_id}".strip(),
            datos=e.datos,
        )
        for e in entradas
    ]
