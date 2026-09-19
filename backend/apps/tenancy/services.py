"""Alta de clientes, invitaciones y gestión de miembros (M0).

Aquí vive lo que Cognito **no** sabe: que un alta crea una organización con su
propietario y su primer sistema, que una invitación caduca, que no puede quedarse una
organización sin propietario y que todo eso deja rastro en el registro encadenado.

Regla de oro del fichero: **una sola transacción por operación**, y si Cognito ya ha
creado el usuario y la transacción se cae, se deshace el alta en el pool. Un usuario en
Cognito sin `Tenant` es un cliente que no puede entrar y que nadie sabe que existe.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.compliance.models import InformeCategorizacion, System
from apps.compliance.services import guardar_valoracion
from apps.tenancy.identity import IdentityError, get_identity
from apps.tenancy.models import (
    AuditLog,
    Invitation,
    Membership,
    MembershipEstado,
    Role,
    Tenant,
    UserIdentity,
)

log = logging.getLogger(__name__)

#: Roles que no pueden operar sin segundo factor (D1). Son quienes aprueban y quienes
#: pueden dejar sin acceso a los demás.
MFA_OBLIGATORIO = (Role.PROPIETARIO, Role.RSEG)

#: Caducidad por defecto de una membresía temporal, si la invitación no dice otra cosa.
DIAS_ACCESO_TEMPORAL = 90

NOMBRE_SISTEMA_POR_DEFECTO = "Sistema de información principal"


class ReglaDeNegocio(Exception):
    """Lo que no se puede hacer por cómo funciona BLENS, no por cómo funciona Cognito."""


@dataclass
class AltaResultado:
    user: object
    tenant: Tenant
    system: System
    #: Aviso para enseñar sin bloquear el alta (p. ej. el resultado anónimo caducó).
    aviso: str = ""


def _user_model():
    return get_user_model()


# --- Alta de un cliente --------------------------------------------------------


@transaction.atomic
def _crear_estructura(*, email, nombre, sub, organizacion, nombre_sistema) -> AltaResultado:
    User = _user_model()
    user = User.objects.create_user(username=email, email=email, password=None)
    # La contraseña vive en Cognito: en Django no hay ninguna que robar.
    user.set_unusable_password()
    if nombre:
        user.first_name = nombre[:150]
    user.save()

    UserIdentity.objects.create(user=user, cognito_sub=sub, email=email, nombre=nombre)
    tenant = Tenant.objects.create(nombre=organizacion)
    Membership.objects.create(tenant=tenant, user=user, role=Role.PROPIETARIO)
    system = System.objects.create(
        tenant=tenant, nombre=nombre_sistema or NOMBRE_SISTEMA_POR_DEFECTO
    )
    return AltaResultado(user=user, tenant=tenant, system=system)


def registrar_cuenta(
    *,
    email: str,
    password: str,
    organizacion: str,
    nombre: str = "",
    nombre_sistema: str = "",
    informe_token: str = "",
    ip=None,
    user_agent: str = "",
) -> AltaResultado:
    """Da de alta a un cliente: usuario en Cognito, organización, propietario y sistema.

    Si se pasa el token de una categorización anónima vigente, se reclama y el sistema
    nace con sus cinco niveles por dimensión. Si ha caducado, **el alta sigue adelante**
    y se devuelve el aviso: no se castiga a quien tardó dos días en decidirse.
    """
    email = email.strip().lower()
    if _user_model().objects.filter(username=email).exists():
        raise IdentityError("Ese correo ya tiene cuenta.", code="email_en_uso")

    identidad = get_identity()
    sub = identidad.registrar(email, password)  # el correo de verificación lo manda el pool
    try:
        resultado = _crear_estructura(
            email=email,
            nombre=nombre,
            sub=sub,
            organizacion=organizacion,
            nombre_sistema=nombre_sistema,
        )
    except Exception:
        # El usuario ya existe en el pool y aquí no hay nada: se deshace. Si esto falla,
        # queda registrado para reconciliarlo a mano antes que dejar un huérfano mudo.
        try:
            identidad.eliminar_usuario(email)
        except Exception:  # pragma: no cover — depende del fallo de AWS
            log.exception("Alta rota: %s existe en Cognito y no en BLENS", email)
        raise

    resultado.aviso = reclamar_informe(
        informe_token, tenant=resultado.tenant, system=resultado.system
    )
    AuditLog.append(
        accion="cuenta.alta",
        tenant=resultado.tenant,
        user=resultado.user,
        objeto=resultado.tenant,
        datos={"email": email, "organizacion": organizacion},
        ip=ip,
        user_agent=user_agent,
    )
    return resultado


def reclamar_informe(token: str, *, tenant: Tenant, system: System) -> str:
    """Convierte una categorización anónima en la del sistema recién creado.

    Devuelve el aviso a enseñar, vacío si todo fue bien.
    """
    if not token:
        return ""
    informe = InformeCategorizacion.objects.filter(token=token, tenant__isnull=True).first()
    if informe is None:
        return "No hemos encontrado esa categorización. Puedes repetirla, son dos minutos."
    if informe.caducado:
        return (
            "Tu categorización había caducado, así que no la hemos podido recuperar. "
            "Puedes repetirla, son dos minutos."
        )
    guardar_valoracion(system, informe.niveles)
    informe.tenant = tenant
    informe.system = system
    informe.expira_en = None  # ya no es de un anónimo: deja de caducar
    informe.save(update_fields=["tenant", "system", "expira_en"])
    return ""


# --- Invitaciones --------------------------------------------------------------


def invitar(
    *,
    tenant: Tenant,
    email: str,
    role: str,
    actor,
    systems: list[int] | None = None,
    bloques: list[str] | None = None,
    membership_dias: int | None = None,
    dias: int = 7,
    ip=None,
    user_agent: str = "",
) -> tuple[Invitation, str]:
    """Emite la invitación y devuelve `(invitacion, token_en_claro)` para el correo."""
    email = email.strip().lower()
    if Membership.objects.filter(tenant=tenant, user__username=email).exists():
        raise ReglaDeNegocio("Esa persona ya pertenece a la organización.")
    if role in (Role.AUDITOR, Role.CONSULTOR) and not membership_dias:
        membership_dias = DIAS_ACCESO_TEMPORAL

    invitacion, token = Invitation.issue(
        tenant=tenant,
        email=email,
        role=role,
        created_by=actor,
        dias=dias,
        systems=systems or [],
        bloques=bloques or [],
        membership_dias=membership_dias,
    )
    AuditLog.append(
        accion="miembro.invitar",
        tenant=tenant,
        user=actor,
        objeto=invitacion,
        datos={"email": email, "role": role, "caduca_en_dias": membership_dias},
        ip=ip,
        user_agent=user_agent,
    )
    return invitacion, token


def invitacion_por_token(token: str) -> Invitation:
    invitacion = Invitation.objects.filter(token_hash=Invitation.hash_token(token)).first()
    if invitacion is None:
        raise ReglaDeNegocio("Esta invitación no existe.")
    if invitacion.used_at is not None:
        raise ReglaDeNegocio("Esta invitación ya se usó.")
    if invitacion.expires_at <= timezone.now():
        raise ReglaDeNegocio("Esta invitación ha caducado. Pide otra a quien te invitó.")
    return invitacion


def aceptar_invitacion(
    *, token: str, password: str = "", nombre: str = "", ip=None, user_agent: str = ""
) -> Membership:
    """Crea (o reutiliza) la cuenta de quien acepta y le da su membresía.

    Reutiliza la cuenta cuando esa persona ya trabaja con otra organización en BLENS:
    una identidad, varias membresías (`docs/roles_y_permisos.md` §1).
    """
    invitacion = invitacion_por_token(token)
    User = _user_model()
    user = User.objects.filter(username=invitacion.email).first()
    identidad = get_identity()
    creado_en_pool = False

    if user is None:
        if not password:
            raise ReglaDeNegocio("Hace falta una contraseña para crear la cuenta.")
        sub = identidad.crear_usuario_invitado(invitacion.email, password)
        creado_en_pool = True
    try:
        with transaction.atomic():
            if user is None:
                user = User.objects.create_user(
                    username=invitacion.email, email=invitacion.email, password=None
                )
                user.set_unusable_password()
                if nombre:
                    user.first_name = nombre[:150]
                user.save()
                UserIdentity.objects.create(
                    user=user, cognito_sub=sub, email=invitacion.email, nombre=nombre
                )

            expira = None
            if invitacion.membership_dias:
                expira = timezone.now() + timedelta(days=invitacion.membership_dias)
            membresia = Membership.objects.create(
                tenant=invitacion.tenant,
                user=user,
                role=invitacion.role,
                bloques=invitacion.bloques,
                expires_at=expira,
                invited_by=invitacion.created_by,
            )
            if invitacion.systems:
                membresia.systems.set(
                    System.objects.filter(tenant=invitacion.tenant, pk__in=invitacion.systems)
                )
            invitacion.used_at = timezone.now()
            invitacion.save(update_fields=["used_at"])
    except Exception:
        if creado_en_pool:
            try:
                identidad.eliminar_usuario(invitacion.email)
            except Exception:  # pragma: no cover
                log.exception("Invitación rota: %s quedó en Cognito", invitacion.email)
        raise

    AuditLog.append(
        accion="miembro.alta",
        tenant=invitacion.tenant,
        user=user,
        objeto=membresia,
        datos={"email": invitacion.email, "role": invitacion.role},
        ip=ip,
        user_agent=user_agent,
    )
    return membresia


# --- Gestión de miembros -------------------------------------------------------


def _propietarios(tenant: Tenant):
    return Membership.objects.filter(
        tenant=tenant, role=Role.PROPIETARIO, estado=MembershipEstado.ACTIVA
    )


def _ultimo_propietario(membresia: Membership) -> bool:
    return (
        membresia.role == Role.PROPIETARIO
        and _propietarios(membresia.tenant).exclude(pk=membresia.pk).count() == 0
    )


def cambiar_rol(
    *, membresia: Membership, role: str, actor, dias: int | None = None, ip=None, user_agent=""
) -> Membership:
    if role != Role.PROPIETARIO and _ultimo_propietario(membresia):
        raise ReglaDeNegocio(
            "Es la única propietaria de la organización. Transfiere antes la propiedad: "
            "si nadie la tiene, nadie puede gestionar usuarios ni facturación."
        )
    anterior = membresia.role
    membresia.role = role
    if role in (Role.AUDITOR, Role.CONSULTOR):
        membresia.expires_at = timezone.now() + timedelta(days=dias or DIAS_ACCESO_TEMPORAL)
    elif dias:
        membresia.expires_at = timezone.now() + timedelta(days=dias)
    membresia.full_clean(exclude=["systems"])
    membresia.save()
    AuditLog.append(
        accion="miembro.rol",
        tenant=membresia.tenant,
        user=actor,
        objeto=membresia,
        datos={"de": anterior, "a": role, "usuario": membresia.user.username},
        ip=ip,
        user_agent=user_agent,
    )
    return membresia


def revocar(*, membresia: Membership, actor, ip=None, user_agent="") -> Membership:
    if _ultimo_propietario(membresia):
        raise ReglaDeNegocio(
            "No puedes revocar a la única propietaria: la organización se quedaría sin "
            "nadie que pueda gestionarla. Transfiere antes la propiedad."
        )
    membresia.estado = MembershipEstado.REVOCADA
    membresia.save(update_fields=["estado"])
    AuditLog.append(
        accion="miembro.revocar",
        tenant=membresia.tenant,
        user=actor,
        objeto=membresia,
        datos={"usuario": membresia.user.username, "role": membresia.role},
        ip=ip,
        user_agent=user_agent,
    )
    return membresia


@transaction.atomic
def transferir_propiedad(*, tenant: Tenant, destino: Membership, actor, ip=None, user_agent=""):
    """El nuevo propietario pasa a serlo y quien transfiere se queda como RSEG.

    No se deja a la organización con dos propietarios por descuido ni con ninguno.
    """
    if not destino.vigente:
        raise ReglaDeNegocio("Esa membresía no está activa.")
    saliente = Membership.objects.filter(tenant=tenant, user=actor).first()
    destino.role = Role.PROPIETARIO
    destino.expires_at = None
    destino.save(update_fields=["role", "expires_at"])
    if saliente is not None and saliente.pk != destino.pk:
        saliente.role = Role.RSEG
        saliente.save(update_fields=["role"])
    AuditLog.append(
        accion="miembro.transferir_propiedad",
        tenant=tenant,
        user=actor,
        objeto=destino,
        datos={"a": destino.user.username},
        ip=ip,
        user_agent=user_agent,
    )
    return destino


def restablecer_mfa(*, membresia: Membership, actor, ip=None, user_agent=""):
    """Quita el segundo factor a quien ha perdido el suyo.

    Cognito no da códigos de recuperación (D1): esta es la única salida, así que queda
    registrada con quién lo hizo y a quién.
    """
    identidad = membresia.user.identidad
    get_identity().restablecer_mfa(identidad.email)
    identidad.mfa_activado = False
    identidad.save(update_fields=["mfa_activado"])
    AuditLog.append(
        accion="miembro.restablecer_mfa",
        tenant=membresia.tenant,
        user=actor,
        objeto=membresia,
        datos={"usuario": identidad.email},
        ip=ip,
        user_agent=user_agent,
    )


def mfa_pendiente(user) -> bool:
    """¿Tiene esta persona un rol que exige segundo factor y aún no lo ha activado?"""
    identidad = UserIdentity.objects.filter(user=user).first()
    if identidad is None or identidad.mfa_activado:
        return False
    return Membership.objects.filter(
        user=user, role__in=MFA_OBLIGATORIO, estado=MembershipEstado.ACTIVA
    ).exists()
