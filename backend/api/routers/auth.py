"""Cuentas y sesión (M0): alta, verificación del correo, sesión, segundo factor,
contraseña e invitaciones.

Las pantallas son de BLENS, no la Hosted UI de Cognito (D1): el alta tiene que poder
enseñar arriba el resultado de la categorización que la persona acaba de obtener, que es
donde se convierte el gancho gratuito.

Los mensajes de error no distinguen «ese correo no existe» de «esa contraseña no es»:
quien pregunta desde fuera no aprende nada de nuestros usuarios.
"""

from __future__ import annotations

from urllib.parse import quote

from apps.tenancy.identity import IdentityError, get_identity
from apps.tenancy.models import AuditLog, Membership, UserIdentity
from apps.tenancy.services import (
    ReglaDeNegocio,
    aceptar_invitacion,
    invitacion_por_token,
    mfa_pendiente,
    registrar_cuenta,
)
from django.conf import settings
from django.http import HttpResponse
from ninja import Router, Schema
from ninja.errors import HttpError
from pydantic import Field

from api.auth import blens_auth, email_normalizado, poner_cookies, quitar_cookies

router = Router(auth=blens_auth)


def _ip(request):
    adelantado = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (adelantado.split(",")[0].strip() or request.META.get("REMOTE_ADDR")) or None


def _agente(request) -> str:
    return request.META.get("HTTP_USER_AGENT", "")[:300]


def _traducir(exc: IdentityError) -> HttpError:
    """Errores del proveedor → códigos HTTP. 429 para lo que es exceso de intentos."""
    if exc.code in ("limite", "bloqueo"):
        return HttpError(429, str(exc))
    if exc.code in ("credenciales", "token", "sesion"):
        return HttpError(401, str(exc))
    return HttpError(400, str(exc))


# --- Alta ----------------------------------------------------------------------


class RegistroIn(Schema):
    email: str
    password: str = Field(min_length=12)
    organizacion: str = Field(min_length=2, max_length=200)
    nombre: str = ""
    nombre_sistema: str = ""
    #: Token de la categorización hecha sin cuenta, si viene de ahí.
    informe_token: str = ""


class RegistroOut(Schema):
    email: str
    organizacion: str
    system_id: int
    #: Vacío si todo fue bien; si no, lo que hay que contarle a la persona.
    aviso: str = ""


@router.post("/register", response={201: RegistroOut}, auth=None, summary="Crear cuenta")
def register(request, datos: RegistroIn):
    """Crea la organización, su propietario y su primer sistema, en una transacción.

    Si trae el token de una categorización anónima vigente, el sistema nace con sus
    niveles por dimensión. Si caducó, el alta **no** se bloquea: se avisa.
    """
    try:
        alta = registrar_cuenta(
            email=email_normalizado(datos.email),
            password=datos.password,
            organizacion=datos.organizacion,
            nombre=datos.nombre,
            nombre_sistema=datos.nombre_sistema,
            informe_token=datos.informe_token,
            ip=_ip(request),
            user_agent=_agente(request),
        )
    except IdentityError as exc:
        raise _traducir(exc) from exc
    return 201, RegistroOut(
        email=alta.user.username,
        organizacion=alta.tenant.nombre,
        system_id=alta.system.pk,
        aviso=alta.aviso,
    )


class ConfirmarIn(Schema):
    email: str
    codigo: str


class OkOut(Schema):
    ok: bool = True
    mensaje: str = ""


@router.post("/confirm", response=OkOut, auth=None, summary="Confirmar el correo")
def confirm(request, datos: ConfirmarIn):
    try:
        get_identity().confirmar_registro(email_normalizado(datos.email), datos.codigo)
    except IdentityError as exc:
        raise _traducir(exc) from exc
    return OkOut(mensaje="Correo confirmado. Ya puedes entrar.")


class EmailIn(Schema):
    email: str


@router.post("/resend", response=OkOut, auth=None, summary="Reenviar el código")
def resend(request, datos: EmailIn):
    try:
        get_identity().reenviar_codigo(email_normalizado(datos.email))
    except IdentityError:
        pass  # no se confirma ni se desmiente que ese correo tenga cuenta
    return OkOut(mensaje="Si ese correo tiene cuenta, le hemos enviado un código.")


# --- Sesión --------------------------------------------------------------------


class LoginIn(Schema):
    email: str
    password: str


class SesionOut(Schema):
    #: True cuando falta el segundo factor: no hay sesión todavía.
    mfa_requerido: bool = False
    sesion: str = ""
    email: str = ""


@router.post("/login", response=SesionOut, auth=None, summary="Iniciar sesión")
def login(request, datos: LoginIn, response: HttpResponse):
    email = email_normalizado(datos.email)
    try:
        resultado = get_identity().iniciar_sesion(email, datos.password)
    except IdentityError as exc:
        raise _traducir(exc) from exc

    if resultado.pendiente_mfa:
        return SesionOut(mfa_requerido=True, sesion=resultado.sesion, email=email)

    poner_cookies(response, resultado)
    _registrar_acceso(request, email)
    return SesionOut(email=email)


class MfaLoginIn(Schema):
    email: str
    codigo: str
    sesion: str


@router.post("/mfa/challenge", response=SesionOut, auth=None, summary="Segundo factor")
def mfa_challenge(request, datos: MfaLoginIn, response: HttpResponse):
    email = email_normalizado(datos.email)
    try:
        resultado = get_identity().responder_mfa(email, datos.codigo, datos.sesion)
    except IdentityError as exc:
        raise _traducir(exc) from exc
    poner_cookies(response, resultado)
    _registrar_acceso(request, email)
    return SesionOut(email=email)


def _registrar_acceso(request, email: str) -> None:
    """El acceso es un hecho auditable (op.exp.8): queda en la cadena de su organización."""
    identidad = UserIdentity.objects.select_related("user").filter(email=email).first()
    if identidad is None:
        return
    membresia = Membership.objects.filter(user=identidad.user).first()
    AuditLog.append(
        accion="cuenta.acceso",
        tenant=membresia.tenant if membresia else None,
        user=identidad.user,
        datos={"email": email},
        ip=_ip(request),
        user_agent=_agente(request),
    )


@router.post("/refresh", response=SesionOut, auth=None, summary="Refrescar la sesión")
def refresh(request, response: HttpResponse):
    token = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE, "")
    if not token:
        raise HttpError(401, "La sesión ha caducado.")
    try:
        resultado = get_identity().refrescar(token)
    except IdentityError as exc:
        quitar_cookies(response)
        raise _traducir(exc) from exc
    poner_cookies(response, resultado)
    return SesionOut()


@router.post("/logout", response=OkOut, summary="Cerrar sesión")
def logout(request, response: HttpResponse):
    try:
        get_identity().cerrar_sesion(getattr(request, "access_token", ""))
    except IdentityError:
        pass  # la cookie se borra igual: por fuera, la sesión se acaba aquí
    quitar_cookies(response)
    return OkOut(mensaje="Sesión cerrada.")


# --- Quién soy -----------------------------------------------------------------


class MembresiaOut(Schema):
    tenant_id: int
    organizacion: str
    role: str
    role_nombre: str
    estado: str
    expires_at: str = ""
    systems: list[int] = []
    bloques: list[str] = []


class YoOut(Schema):
    email: str
    nombre: str
    mfa_activado: bool
    mfa_pendiente: bool
    membresias: list[MembresiaOut]


@router.get("/me", response=YoOut, summary="Quién soy")
def me(request):
    identidad = request.identidad
    membresias = (
        Membership.objects.filter(user=request.user)
        .select_related("tenant")
        .prefetch_related("systems")
    )
    return YoOut(
        email=identidad.email,
        nombre=identidad.nombre or request.user.first_name,
        mfa_activado=identidad.mfa_activado,
        mfa_pendiente=mfa_pendiente(request.user),
        membresias=[
            MembresiaOut(
                tenant_id=m.tenant_id,
                organizacion=m.tenant.nombre,
                role=m.role,
                role_nombre=m.get_role_display(),
                estado=m.estado,
                expires_at=m.expires_at.isoformat() if m.expires_at else "",
                systems=[s.pk for s in m.systems.all()],
                bloques=m.bloques,
            )
            for m in membresias
        ],
    )


# --- Contraseña ----------------------------------------------------------------


@router.post("/password/forgot", response=OkOut, auth=None, summary="Olvidé la contraseña")
def password_forgot(request, datos: EmailIn):
    try:
        get_identity().olvide_contrasena(email_normalizado(datos.email))
    except IdentityError:
        pass  # misma respuesta exista o no la cuenta
    return OkOut(mensaje="Si ese correo tiene cuenta, le hemos enviado un código.")


class PasswordResetIn(Schema):
    email: str
    codigo: str
    password: str = Field(min_length=12)


@router.post("/password/reset", response=OkOut, auth=None, summary="Nueva contraseña")
def password_reset(request, datos: PasswordResetIn):
    try:
        get_identity().confirmar_contrasena(
            email_normalizado(datos.email), datos.codigo, datos.password
        )
    except IdentityError as exc:
        raise _traducir(exc) from exc
    return OkOut(mensaje="Contraseña cambiada. Ya puedes entrar con ella.")


# --- Segundo factor ------------------------------------------------------------


class MfaSetupOut(Schema):
    secreto: str
    #: Lo que se convierte en QR en el navegador. El secreto también se enseña en texto,
    #: para quien no pueda escanear.
    otpauth_uri: str
    aviso: str


@router.post("/mfa/setup", response=MfaSetupOut, summary="Empezar el alta del segundo factor")
def mfa_setup(request):
    identidad = request.identidad
    try:
        secreto = get_identity().iniciar_alta_mfa(request.access_token)
    except IdentityError as exc:
        raise _traducir(exc) from exc
    etiqueta = quote(f"BLENS:{identidad.email}")
    return MfaSetupOut(
        secreto=secreto,
        otpauth_uri=f"otpauth://totp/{etiqueta}?secret={secreto}&issuer=BLENS",
        aviso=(
            "Guarda el acceso a tu aplicación de códigos. No hay códigos de recuperación: "
            "si pierdes el móvil, tendrá que restablecértelo el propietario de tu "
            "organización."
        ),
    )


class CodigoIn(Schema):
    codigo: str


@router.post("/mfa/verify", response=OkOut, summary="Confirmar el segundo factor")
def mfa_verify(request, datos: CodigoIn):
    identidad = request.identidad
    try:
        get_identity().confirmar_alta_mfa(request.access_token, datos.codigo)
    except IdentityError as exc:
        raise _traducir(exc) from exc
    identidad.mfa_activado = True
    identidad.save(update_fields=["mfa_activado"])
    membresia = Membership.objects.filter(user=request.user).first()
    AuditLog.append(
        accion="cuenta.mfa_activado",
        tenant=membresia.tenant if membresia else None,
        user=request.user,
        datos={"email": identidad.email},
        ip=_ip(request),
        user_agent=_agente(request),
    )
    return OkOut(mensaje="Verificación en dos pasos activada.")


# --- Invitaciones (lo que ve quien las recibe) ---------------------------------


class InvitacionOut(Schema):
    organizacion: str
    email: str
    role: str
    role_nombre: str
    invitado_por: str = ""
    caduca: str
    #: True si esa persona ya tiene cuenta en BLENS: entonces no se le pide contraseña.
    tiene_cuenta: bool


@router.get("/invitation/{token}", response=InvitacionOut, auth=None, summary="Ver la invitación")
def invitation(request, token: str):
    try:
        inv = invitacion_por_token(token)
    except ReglaDeNegocio as exc:
        raise HttpError(410, str(exc)) from exc
    return InvitacionOut(
        organizacion=inv.tenant.nombre,
        email=inv.email,
        role=inv.role,
        role_nombre=inv.get_role_display(),
        invitado_por=getattr(inv.created_by, "username", ""),
        caduca=inv.expires_at.isoformat(),
        tiene_cuenta=UserIdentity.objects.filter(email=inv.email).exists(),
    )


class AceptarIn(Schema):
    password: str = ""
    nombre: str = ""


class AceptadaOut(Schema):
    organizacion: str
    role: str
    email: str


@router.post(
    "/invitation/{token}/accept",
    response={201: AceptadaOut},
    auth=None,
    summary="Aceptar la invitación",
)
def invitation_accept(request, token: str, datos: AceptarIn):
    try:
        membresia = aceptar_invitacion(
            token=token,
            password=datos.password,
            nombre=datos.nombre,
            ip=_ip(request),
            user_agent=_agente(request),
        )
    except ReglaDeNegocio as exc:
        raise HttpError(410, str(exc)) from exc
    except IdentityError as exc:
        raise _traducir(exc) from exc
    return 201, AceptadaOut(
        organizacion=membresia.tenant.nombre,
        role=membresia.role,
        email=membresia.user.username,
    )
