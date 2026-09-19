"""Única puerta a Cognito (D1). **Nadie más llama a AWS para autenticar.**

Tres razones para que todo pase por aquí:

1. **La CI no llama a AWS** (criterio de cierre de F3b). `FakeIdentity` implementa el
   mismo contrato en memoria, así que los tests ejercitan el flujo entero sin red.
2. Cognito **solo autentica**. El rol no viaja en el token: se lee de `Membership` y lo
   resuelve `can()` (§5). Aquí no se decide nada de permisos.
3. Si algún día se cambia de proveedor de identidad, el punto de enganche es este
   fichero y no ciento y pico de vistas.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field
from functools import lru_cache

from django.conf import settings


class IdentityError(Exception):
    """Fallo del proveedor de identidad, ya traducido a algo que se puede enseñar.

    `code` es estable y lo consume la API; `args[0]` es el texto para la persona.
    """

    def __init__(self, mensaje: str, *, code: str = "identidad"):
        super().__init__(mensaje)
        self.code = code


@dataclass(frozen=True)
class IdentityClaims:
    """Lo poco que nos interesa de un token verificado."""

    sub: str
    email: str = ""


@dataclass
class AuthResult:
    """Resultado de un intento de inicio de sesión.

    O trae tokens, o trae un desafío pendiente (hoy solo el segundo factor), nunca
    las dos cosas.
    """

    access_token: str = ""
    refresh_token: str = ""
    expires_in: int = 0
    desafio: str = ""  # 'SOFTWARE_TOKEN_MFA' | 'MFA_SETUP' | ''
    sesion: str = ""

    @property
    def pendiente_mfa(self) -> bool:
        return bool(self.desafio)


class IdentityProvider:
    """Contrato que cumplen Cognito y el doble de los tests."""

    # --- alta y verificación del correo ---
    def registrar(self, email: str, password: str) -> str:  # devuelve el `sub`
        raise NotImplementedError

    def confirmar_registro(self, email: str, codigo: str) -> None:
        raise NotImplementedError

    def reenviar_codigo(self, email: str) -> None:
        raise NotImplementedError

    # --- sesión ---
    def iniciar_sesion(self, email: str, password: str) -> AuthResult:
        raise NotImplementedError

    def responder_mfa(self, email: str, codigo: str, sesion: str) -> AuthResult:
        raise NotImplementedError

    def refrescar(self, refresh_token: str) -> AuthResult:
        raise NotImplementedError

    def cerrar_sesion(self, access_token: str) -> None:
        raise NotImplementedError

    def verificar_token(self, token: str) -> IdentityClaims:
        raise NotImplementedError

    # --- contraseña ---
    def olvide_contrasena(self, email: str) -> None:
        raise NotImplementedError

    def confirmar_contrasena(self, email: str, codigo: str, nueva: str) -> None:
        raise NotImplementedError

    # --- segundo factor ---
    def iniciar_alta_mfa(self, access_token: str) -> str:  # secreto TOTP en base32
        raise NotImplementedError

    def confirmar_alta_mfa(self, access_token: str, codigo: str) -> None:
        raise NotImplementedError

    def restablecer_mfa(self, email: str) -> None:
        """Desactiva el segundo factor de alguien que ha perdido el suyo.

        Cognito **no da códigos de recuperación** (D1), así que esta es la única salida
        y por eso es una acción con permiso propio y traza.
        """
        raise NotImplementedError

    # --- administración ---
    def crear_usuario_invitado(self, email: str, password: str) -> str:
        """Alta de quien llega por invitación: sin código de verificación por correo,
        porque el enlace de la invitación ya demuestra que controla ese buzón."""
        raise NotImplementedError

    def eliminar_usuario(self, email: str) -> None:
        """Solo para deshacer un alta que se rompió a media transacción."""
        raise NotImplementedError


# --- Cognito ------------------------------------------------------------------


class CognitoIdentity(IdentityProvider):
    """Implementación real. Todas las llamadas a boto3 del producto viven aquí."""

    def __init__(self, *, user_pool_id: str, client_id: str, client_secret: str = "", region: str):
        self.user_pool_id = user_pool_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.region = region
        self._jwks: dict | None = None

    @property
    def _client(self):
        import boto3

        return boto3.client("cognito-idp", region_name=self.region)

    def _secret_hash(self, email: str) -> dict[str, str]:
        if not self.client_secret:
            return {}
        firma = hmac.new(
            self.client_secret.encode("utf-8"),
            (email + self.client_id).encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return {"SecretHash": base64.b64encode(firma).decode("ascii")}

    def _traducir(self, exc: Exception) -> IdentityError:
        """Errores de Cognito → mensajes que se pueden enseñar sin filtrar de más."""
        code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
        mensajes = {
            "UsernameExistsException": ("Ese correo ya tiene cuenta.", "email_en_uso"),
            "NotAuthorizedException": ("Correo o contraseña incorrectos.", "credenciales"),
            "UserNotFoundException": ("Correo o contraseña incorrectos.", "credenciales"),
            "CodeMismatchException": ("El código no es correcto.", "codigo"),
            "ExpiredCodeException": ("El código ha caducado. Pide uno nuevo.", "codigo"),
            "InvalidPasswordException": (
                "La contraseña no cumple la política de seguridad.",
                "password",
            ),
            "TooManyRequestsException": ("Demasiados intentos. Prueba en unos minutos.", "limite"),
            "TooManyFailedAttemptsException": (
                "Demasiados intentos fallidos. La cuenta queda bloqueada un rato.",
                "bloqueo",
            ),
            "UserNotConfirmedException": (
                "Aún no has confirmado tu correo. Mira el mensaje que te enviamos.",
                "sin_confirmar",
            ),
        }
        mensaje, propio = mensajes.get(
            code, ("No se ha podido completar la operación.", "identidad")
        )
        return IdentityError(mensaje, code=propio)

    def _llamar(self, nombre: str, **kwargs):
        try:
            return getattr(self._client, nombre)(**kwargs)
        except Exception as exc:  # boto3 lanza clases generadas en tiempo de ejecución
            raise self._traducir(exc) from exc

    # --- alta ---
    def registrar(self, email: str, password: str) -> str:
        r = self._llamar(
            "sign_up",
            ClientId=self.client_id,
            Username=email,
            Password=password,
            UserAttributes=[{"Name": "email", "Value": email}],
            **self._secret_hash(email),
        )
        return r["UserSub"]

    def confirmar_registro(self, email: str, codigo: str) -> None:
        self._llamar(
            "confirm_sign_up",
            ClientId=self.client_id,
            Username=email,
            ConfirmationCode=codigo,
            **self._secret_hash(email),
        )

    def reenviar_codigo(self, email: str) -> None:
        self._llamar(
            "resend_confirmation_code",
            ClientId=self.client_id,
            Username=email,
            **self._secret_hash(email),
        )

    # --- sesión ---
    def _resultado(self, respuesta: dict, email: str) -> AuthResult:
        desafio = respuesta.get("ChallengeName", "")
        if desafio:
            return AuthResult(desafio=desafio, sesion=respuesta.get("Session", ""))
        auth = respuesta["AuthenticationResult"]
        return AuthResult(
            access_token=auth["AccessToken"],
            refresh_token=auth.get("RefreshToken", ""),
            expires_in=auth.get("ExpiresIn", 0),
        )

    def iniciar_sesion(self, email: str, password: str) -> AuthResult:
        r = self._llamar(
            "initiate_auth",
            ClientId=self.client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": email, "PASSWORD": password, **self._secret_hash(email)},
        )
        return self._resultado(r, email)

    def responder_mfa(self, email: str, codigo: str, sesion: str) -> AuthResult:
        r = self._llamar(
            "respond_to_auth_challenge",
            ClientId=self.client_id,
            ChallengeName="SOFTWARE_TOKEN_MFA",
            Session=sesion,
            ChallengeResponses={
                "USERNAME": email,
                "SOFTWARE_TOKEN_MFA_CODE": codigo,
                **self._secret_hash(email),
            },
        )
        return self._resultado(r, email)

    def refrescar(self, refresh_token: str) -> AuthResult:
        r = self._llamar(
            "initiate_auth",
            ClientId=self.client_id,
            AuthFlow="REFRESH_TOKEN_AUTH",
            AuthParameters={"REFRESH_TOKEN": refresh_token},
        )
        return self._resultado(r, "")

    def cerrar_sesion(self, access_token: str) -> None:
        self._llamar("global_sign_out", AccessToken=access_token)

    def verificar_token(self, token: str) -> IdentityClaims:
        import jwt
        from jwt import PyJWKClient

        if self._jwks is None:
            url = (
                f"https://cognito-idp.{self.region}.amazonaws.com/"
                f"{self.user_pool_id}/.well-known/jwks.json"
            )
            self._jwks = {"cliente": PyJWKClient(url, cache_keys=True)}
        try:
            clave = self._jwks["cliente"].get_signing_key_from_jwt(token).key
            datos = jwt.decode(
                token,
                clave,
                algorithms=["RS256"],
                issuer=(f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}"),
                options={"verify_aud": False},  # el access token de Cognito no lleva `aud`
            )
        except Exception as exc:
            raise IdentityError("Token no válido.", code="token") from exc
        # `client_id` es el equivalente a `aud` en el access token: se comprueba a mano.
        if datos.get("client_id") not in ("", None, self.client_id):
            raise IdentityError("Token emitido para otra aplicación.", code="token")
        if datos.get("token_use") != "access":
            raise IdentityError("Ese token no sirve para autenticar.", code="token")
        return IdentityClaims(sub=datos["sub"], email=datos.get("username", ""))

    # --- contraseña ---
    def olvide_contrasena(self, email: str) -> None:
        self._llamar(
            "forgot_password",
            ClientId=self.client_id,
            Username=email,
            **self._secret_hash(email),
        )

    def confirmar_contrasena(self, email: str, codigo: str, nueva: str) -> None:
        self._llamar(
            "confirm_forgot_password",
            ClientId=self.client_id,
            Username=email,
            ConfirmationCode=codigo,
            Password=nueva,
            **self._secret_hash(email),
        )

    # --- segundo factor ---
    def iniciar_alta_mfa(self, access_token: str) -> str:
        return self._llamar("associate_software_token", AccessToken=access_token)["SecretCode"]

    def confirmar_alta_mfa(self, access_token: str, codigo: str) -> None:
        r = self._llamar("verify_software_token", AccessToken=access_token, UserCode=codigo)
        if r.get("Status") != "SUCCESS":
            raise IdentityError("El código no es correcto.", code="codigo")
        self._llamar(
            "set_user_mfa_preference",
            AccessToken=access_token,
            SoftwareTokenMfaSettings={"Enabled": True, "PreferredMfa": True},
        )

    def restablecer_mfa(self, email: str) -> None:
        self._llamar(
            "admin_set_user_mfa_preference",
            UserPoolId=self.user_pool_id,
            Username=email,
            SoftwareTokenMfaSettings={"Enabled": False, "PreferredMfa": False},
        )

    # --- administración ---
    def crear_usuario_invitado(self, email: str, password: str) -> str:
        r = self._llamar(
            "admin_create_user",
            UserPoolId=self.user_pool_id,
            Username=email,
            MessageAction="SUPPRESS",  # el correo lo manda BLENS con su invitación
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
            ],
        )
        self._llamar(
            "admin_set_user_password",
            UserPoolId=self.user_pool_id,
            Username=email,
            Password=password,
            Permanent=True,
        )
        for attr in r["User"]["Attributes"]:
            if attr["Name"] == "sub":
                return attr["Value"]
        raise IdentityError("Cognito no devolvió el identificador del usuario.")

    def eliminar_usuario(self, email: str) -> None:
        self._llamar("admin_delete_user", UserPoolId=self.user_pool_id, Username=email)


# --- Doble para desarrollo y tests --------------------------------------------


@dataclass
class _Cuenta:
    sub: str
    password: str
    confirmado: bool = False
    codigo: str = "123456"
    mfa_secreto: str = ""
    mfa_activo: bool = False
    sesiones: set[str] = field(default_factory=set)


class FakeIdentity(IdentityProvider):
    """Cognito en memoria, con la misma semántica en lo que importa.

    Reproduce a propósito lo que muerde: no se inicia sesión sin confirmar el correo,
    con MFA activo la contraseña **no basta** y devuelve un desafío, y el código de
    verificación se equivoca si no es el que toca. Los tokens son opacos: quien los
    verifica es este mismo objeto.
    """

    CODIGO_MFA = "654321"

    def __init__(self):
        self.cuentas: dict[str, _Cuenta] = {}
        self._tokens: dict[str, tuple[str, float]] = {}  # token → (email, caduca_en)
        self._refrescos: dict[str, str] = {}
        self._desafios: dict[str, str] = {}  # sesión → email
        self.correos: list[tuple[str, str]] = []  # (email, asunto) — para asertar en tests

    # --- utilidades internas ---
    def _cuenta(self, email: str) -> _Cuenta:
        cuenta = self.cuentas.get(email)
        if cuenta is None:
            raise IdentityError("Correo o contraseña incorrectos.", code="credenciales")
        return cuenta

    def _emitir(self, email: str) -> AuthResult:
        access = secrets.token_urlsafe(24)
        refresh = secrets.token_urlsafe(24)
        self._tokens[access] = (email, time.time() + 3600)
        self._refrescos[refresh] = email
        return AuthResult(access_token=access, refresh_token=refresh, expires_in=3600)

    def email_de(self, access_token: str) -> str:
        return self._tokens[access_token][0]

    # --- alta ---
    def registrar(self, email: str, password: str) -> str:
        if email in self.cuentas:
            raise IdentityError("Ese correo ya tiene cuenta.", code="email_en_uso")
        if len(password) < 12:
            raise IdentityError(
                "La contraseña no cumple la política de seguridad.", code="password"
            )
        sub = f"sub-{len(self.cuentas) + 1}-{secrets.token_hex(4)}"
        self.cuentas[email] = _Cuenta(sub=sub, password=password)
        self.correos.append((email, "confirma tu correo"))
        return sub

    def confirmar_registro(self, email: str, codigo: str) -> None:
        cuenta = self._cuenta(email)
        if codigo != cuenta.codigo:
            raise IdentityError("El código no es correcto.", code="codigo")
        cuenta.confirmado = True

    def reenviar_codigo(self, email: str) -> None:
        self._cuenta(email)
        self.correos.append((email, "confirma tu correo"))

    # --- sesión ---
    def iniciar_sesion(self, email: str, password: str) -> AuthResult:
        cuenta = self._cuenta(email)
        if password != cuenta.password:
            raise IdentityError("Correo o contraseña incorrectos.", code="credenciales")
        if not cuenta.confirmado:
            raise IdentityError(
                "Aún no has confirmado tu correo. Mira el mensaje que te enviamos.",
                code="sin_confirmar",
            )
        if cuenta.mfa_activo:
            sesion = secrets.token_urlsafe(16)
            self._desafios[sesion] = email
            return AuthResult(desafio="SOFTWARE_TOKEN_MFA", sesion=sesion)
        return self._emitir(email)

    def responder_mfa(self, email: str, codigo: str, sesion: str) -> AuthResult:
        if self._desafios.get(sesion) != email:
            raise IdentityError("La sesión de verificación ha caducado.", code="sesion")
        if codigo != self.CODIGO_MFA:
            raise IdentityError("El código no es correcto.", code="codigo")
        del self._desafios[sesion]
        return self._emitir(email)

    def refrescar(self, refresh_token: str) -> AuthResult:
        email = self._refrescos.get(refresh_token)
        if email is None:
            raise IdentityError("La sesión ha caducado.", code="token")
        return self._emitir(email)

    def cerrar_sesion(self, access_token: str) -> None:
        self._tokens.pop(access_token, None)

    def verificar_token(self, token: str) -> IdentityClaims:
        dato = self._tokens.get(token)
        if dato is None:
            raise IdentityError("Token no válido.", code="token")
        email, caduca = dato
        if caduca <= time.time():
            del self._tokens[token]
            raise IdentityError("El token ha caducado.", code="token")
        return IdentityClaims(sub=self._cuenta(email).sub, email=email)

    # --- contraseña ---
    def olvide_contrasena(self, email: str) -> None:
        self._cuenta(email)
        self.correos.append((email, "restablecer contraseña"))

    def confirmar_contrasena(self, email: str, codigo: str, nueva: str) -> None:
        cuenta = self._cuenta(email)
        if codigo != cuenta.codigo:
            raise IdentityError("El código no es correcto.", code="codigo")
        if len(nueva) < 12:
            raise IdentityError(
                "La contraseña no cumple la política de seguridad.", code="password"
            )
        cuenta.password = nueva

    # --- segundo factor ---
    def iniciar_alta_mfa(self, access_token: str) -> str:
        cuenta = self._cuenta(self.email_de(access_token))
        cuenta.mfa_secreto = base64.b32encode(secrets.token_bytes(20)).decode("ascii")
        return cuenta.mfa_secreto

    def confirmar_alta_mfa(self, access_token: str, codigo: str) -> None:
        cuenta = self._cuenta(self.email_de(access_token))
        if codigo != self.CODIGO_MFA:
            raise IdentityError("El código no es correcto.", code="codigo")
        cuenta.mfa_activo = True

    def restablecer_mfa(self, email: str) -> None:
        cuenta = self._cuenta(email)
        cuenta.mfa_activo = False
        cuenta.mfa_secreto = ""

    # --- administración ---
    def crear_usuario_invitado(self, email: str, password: str) -> str:
        sub = self.registrar(email, password)
        self.cuentas[email].confirmado = True
        return sub

    def eliminar_usuario(self, email: str) -> None:
        self.cuentas.pop(email, None)


@lru_cache(maxsize=1)
def _proveedor_real() -> IdentityProvider:
    cfg = settings.COGNITO
    if not cfg.get("USER_POOL_ID") or not cfg.get("CLIENT_ID"):
        raise IdentityError(
            "Cognito no está configurado: faltan COGNITO_USER_POOL_ID o COGNITO_CLIENT_ID."
        )
    return CognitoIdentity(
        user_pool_id=cfg["USER_POOL_ID"],
        client_id=cfg["CLIENT_ID"],
        client_secret=cfg.get("CLIENT_SECRET", ""),
        region=cfg.get("REGION") or settings.AWS_REGION,
    )


_fake: FakeIdentity | None = None


def get_identity() -> IdentityProvider:
    """Proveedor vigente. Con `COGNITO['FAKE']`, el doble en memoria (desarrollo y tests)."""
    global _fake
    if settings.COGNITO.get("FAKE"):
        if _fake is None:
            _fake = FakeIdentity()
        return _fake
    return _proveedor_real()


def reset_identity() -> None:
    """Vacía el doble entre tests. No toca el proveedor real."""
    global _fake
    _fake = None
    _proveedor_real.cache_clear()
