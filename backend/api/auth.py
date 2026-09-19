"""Autenticación de la API: el token de Cognito, verificado en cada petición.

Sustituye al `django_auth` provisional de F0–F3 (D1). Dos formas de presentar el token,
con la misma comprobación detrás:

* **Cookie `HttpOnly`** (`settings.AUTH_COOKIE`), que es como entra el frontend. Al ser
  una credencial ambiental, exige CSRF: lo impone `APIKeyCookie`.
* **Cabecera `Authorization: Bearer`**, para clientes de API y para los tests. No es
  ambiental, así que no necesita CSRF.

Aquí **no se decide ningún permiso**: esto solo dice quién es. El rol y el ámbito los
resuelve `can()` (§15). Lo único que se impone además de la identidad es el segundo
factor, porque un propietario sin MFA no debería poder operar (D1) y este es el único
sitio por el que pasan todas las peticiones.
"""

from __future__ import annotations

from apps.tenancy.identity import IdentityError, get_identity
from apps.tenancy.models import UserIdentity
from apps.tenancy.services import mfa_pendiente
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from ninja.errors import HttpError
from ninja.security import APIKeyCookie, HttpBearer

#: Lo que se puede hacer teniendo cuenta pero aún sin segundo factor: justamente,
#: activarlo. Y saber quién eres y salir.
RUTAS_SIN_MFA = (
    "/api/auth/me",
    "/api/auth/logout",
    "/api/auth/refresh",
    "/api/auth/mfa/setup",
    "/api/auth/mfa/verify",
)


def _resolver(request, token: str | None):
    """Token → usuario de Django, o `None` si no hay manera."""
    if not token:
        return None
    try:
        claims = get_identity().verificar_token(token)
    except IdentityError:
        return None

    identidad = UserIdentity.objects.select_related("user").filter(cognito_sub=claims.sub).first()
    if identidad is None or not identidad.user.is_active:
        return None

    request.identidad = identidad
    request.access_token = token
    # Ninja deja el resultado en `request.auth`, pero medio backend (y `can()`) habla de
    # `request.user`, que con token es el anónimo del middleware de sesión. Se fija aquí,
    # en el único sitio por el que pasan todas las peticiones.
    request.user = identidad.user
    if request.path not in RUTAS_SIN_MFA and mfa_pendiente(identidad.user):
        raise HttpError(
            403,
            "Tu rol exige verificación en dos pasos. Actívala para seguir: es cosa de un "
            "minuto y sin ella no podemos dejarte operar.",
        )
    return identidad.user


class CookieAuth(APIKeyCookie):
    """Cookie HttpOnly. Credencial ambiental, luego con comprobación CSRF."""

    param_name = settings.AUTH_COOKIE

    def authenticate(self, request, key):
        return _resolver(request, key)


class BearerAuth(HttpBearer):
    """`Authorization: Bearer <token>`. Sin CSRF: no viaja sola."""

    def authenticate(self, request, token):
        return _resolver(request, token)


#: Lo que se pone en `Router(auth=...)`. Un solo sitio, para que añadir un router nuevo
#: no invente su propia forma de autenticar.
blens_auth = [CookieAuth(), BearerAuth()]


def poner_cookies(response, resultado) -> None:
    """Guarda los tokens en cookies HttpOnly. El navegador nunca ve el valor."""
    comun = {
        "httponly": True,
        "secure": not settings.DEBUG,
        "samesite": settings.AUTH_COOKIE_SAMESITE,
        "path": "/",
    }
    response.set_cookie(
        settings.AUTH_COOKIE,
        resultado.access_token,
        max_age=resultado.expires_in or 3600,
        **comun,
    )
    if resultado.refresh_token:
        response.set_cookie(
            settings.AUTH_REFRESH_COOKIE,
            resultado.refresh_token,
            max_age=60 * 60 * 24 * 30,
            **comun,
        )


def quitar_cookies(response) -> None:
    for nombre in (settings.AUTH_COOKIE, settings.AUTH_REFRESH_COOKIE):
        response.delete_cookie(nombre, path="/")


def email_normalizado(valor: str) -> str:
    """Valida y normaliza un correo con el validador de Django.

    Se usa el de Django y no `pydantic.EmailStr` para no añadir `email-validator` al
    proyecto por esto: es el mismo criterio que aplica `EmailField` en los modelos.
    """
    valor = (valor or "").strip().lower()
    try:
        validate_email(valor)
    except ValidationError as exc:
        raise HttpError(400, "Ese correo no tiene buena pinta. Revísalo.") from exc
    return valor
