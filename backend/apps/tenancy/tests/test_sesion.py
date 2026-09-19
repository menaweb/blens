"""Sesión y segundo factor (M0).

Lo que se prueba es lo que separa una sesión de verdad de un formulario bonito: que no
se entra sin confirmar el correo, que con MFA la contraseña **no basta**, que un token
inservible no abre nada, y que quien tiene un rol de los que aprueban no puede operar
hasta activar el segundo factor.
"""

import json

import pytest
from django.conf import settings
from django.test import Client

from apps.tenancy.identity import get_identity
from apps.tenancy.models import AuditLog, Role, UserIdentity
from apps.tenancy.testing import PASSWORD, como

PUBLICO = Client()


def post(url, payload, cliente=None):
    return (cliente or Client()).post(
        url, data=json.dumps(payload), content_type="application/json"
    )


@pytest.fixture
def propietario(miembro, usuarios):
    return miembro(Role.PROPIETARIO)


def test_no_se_entra_sin_confirmar_el_correo(db):
    get_identity().registrar("nuevo@ejemplo.test", PASSWORD)

    respuesta = post("/api/auth/login", {"email": "nuevo@ejemplo.test", "password": PASSWORD})

    assert respuesta.status_code == 400
    assert "confirmado" in respuesta.json()["detail"]


def test_entrar_deja_el_token_en_una_cookie_httponly(db, propietario):
    respuesta = post("/api/auth/login", {"email": propietario.username, "password": PASSWORD})

    assert respuesta.status_code == 200
    cookie = respuesta.cookies[settings.AUTH_COOKIE]
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "Lax"
    # El navegador no ve el token: no hay nada que un XSS pueda leer de localStorage.
    assert cookie.value


def test_una_contrasena_equivocada_no_dice_si_el_correo_existe(db, propietario):
    de_alguien = post(
        "/api/auth/login", {"email": propietario.username, "password": "xxxxxxxxxxxx"}
    )
    de_nadie = post("/api/auth/login", {"email": "nadie@ejemplo.test", "password": "xxxxxxxxxxxx"})

    assert de_alguien.status_code == de_nadie.status_code == 401
    assert de_alguien.json()["detail"] == de_nadie.json()["detail"]


def test_con_segundo_factor_la_contrasena_no_basta(db, propietario):
    identidad = get_identity()
    identidad.cuentas[propietario.username].mfa_activo = True

    primero = post("/api/auth/login", {"email": propietario.username, "password": PASSWORD})

    assert primero.json()["mfa_requerido"] is True
    assert settings.AUTH_COOKIE not in primero.cookies
    sesion = primero.json()["sesion"]

    malo = post(
        "/api/auth/mfa/challenge",
        {"email": propietario.username, "codigo": "000000", "sesion": sesion},
    )
    assert malo.status_code == 400

    bueno = post(
        "/api/auth/mfa/challenge",
        {
            "email": propietario.username,
            "codigo": identidad.CODIGO_MFA,
            "sesion": sesion,
        },
    )
    assert bueno.status_code == 200
    assert bueno.cookies[settings.AUTH_COOKIE].value


def test_el_acceso_queda_registrado(db, propietario, tenant):
    post("/api/auth/login", {"email": propietario.username, "password": PASSWORD})

    entrada = AuditLog.objects.filter(accion="cuenta.acceso").get()
    assert entrada.datos["email"] == propietario.username
    assert entrada.tenant == tenant


@pytest.mark.parametrize(
    "token, motivo",
    [("basura", "inventado"), ("", "vacío")],
)
def test_un_token_que_no_vale_no_abre_nada(db, token, motivo):
    cliente = Client(HTTP_AUTHORIZATION=f"Bearer {token}")

    assert cliente.get("/api/systems").status_code == 401, motivo


def test_un_token_caducado_deja_de_valer(db, propietario):
    identidad = get_identity()
    resultado = identidad.iniciar_sesion(propietario.username, PASSWORD)
    cliente = Client(HTTP_AUTHORIZATION=f"Bearer {resultado.access_token}")
    assert cliente.get("/api/systems").status_code == 200

    # Lo que haría el paso del tiempo, sin esperar una hora.
    identidad._tokens[resultado.access_token] = (propietario.username, 0)

    assert cliente.get("/api/systems").status_code == 401


def test_el_token_de_una_cuenta_borrada_no_sirve(db, propietario):
    cliente = como(propietario)
    UserIdentity.objects.filter(user=propietario).delete()

    assert cliente.get("/api/systems").status_code == 401


def test_un_propietario_sin_segundo_factor_no_puede_operar_pero_si_activarlo(db, propietario):
    UserIdentity.objects.filter(user=propietario).update(mfa_activado=False)
    cliente = como(propietario)

    assert cliente.get("/api/systems").status_code == 403

    alta = cliente.post("/api/auth/mfa/setup")
    assert alta.status_code == 200
    assert alta.json()["otpauth_uri"].startswith("otpauth://totp/")
    assert "no hay códigos de recuperación" in alta.json()["aviso"].lower()

    verificado = post(
        "/api/auth/mfa/verify", {"codigo": get_identity().CODIGO_MFA}, cliente=cliente
    )
    assert verificado.status_code == 200
    assert UserIdentity.objects.get(user=propietario).mfa_activado is True
    assert cliente.get("/api/systems").status_code == 200


def test_al_tecnico_no_se_le_exige_segundo_factor(db, miembro):
    """El MFA es obligatorio para quien aprueba, no para todo el mundo (D1)."""
    tecnico = miembro(Role.TECNICO)
    UserIdentity.objects.filter(user=tecnico).update(mfa_activado=False)

    assert como(tecnico).get("/api/systems").status_code == 200


def test_cerrar_sesion_borra_la_cookie_e_invalida_el_token(db, propietario):
    entrada = post("/api/auth/login", {"email": propietario.username, "password": PASSWORD})
    token = entrada.cookies[settings.AUTH_COOKIE].value
    cliente = Client(HTTP_AUTHORIZATION=f"Bearer {token}")

    salida = cliente.post("/api/auth/logout")

    assert salida.status_code == 200
    assert salida.cookies[settings.AUTH_COOKIE].value == ""
    assert cliente.get("/api/systems").status_code == 401


def test_quien_soy_cuenta_las_membresias(db, propietario, tenant):
    respuesta = como(propietario).get("/api/auth/me")

    datos = respuesta.json()
    assert datos["email"] == propietario.username
    assert datos["mfa_activado"] is True
    assert datos["membresias"][0]["organizacion"] == tenant.nombre
    assert datos["membresias"][0]["role"] == Role.PROPIETARIO
