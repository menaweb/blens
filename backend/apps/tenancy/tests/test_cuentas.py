"""Alta de un cliente (M0): organización, propietario, primer sistema y conversión
del resultado de la categorización anónima.

Es el paso donde el gancho gratuito se convierte en cliente, así que lo que se prueba
aquí no es que «funcione el registro», sino que **no se pierde nada por el camino** y
que un fallo a mitad no deja restos.
"""

import json
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from apps.compliance.models import DimensionValuation, InformeCategorizacion, System
from apps.compliance.services import crear_informe
from apps.tenancy import services
from apps.tenancy.identity import IdentityError, get_identity
from apps.tenancy.models import AuditLog, Membership, Role, Tenant, UserIdentity

ALTA = {
    "email": "rseg@ayuntamiento.test",
    "password": "contrasena-larga-1",
    "organizacion": "Ayuntamiento de Ejemplo",
    "nombre": "Rafa",
}


def registrar(cliente=None, **extra):
    cliente = cliente or Client()
    return cliente.post(
        "/api/auth/register",
        data=json.dumps({**ALTA, **extra}),
        content_type="application/json",
    )


@pytest.fixture
def informe_anonimo(db, catalogo):
    return crear_informe(
        {"C": "MEDIO", "I": "MEDIO", "T": "BAJO", "A": "ALTO", "D": "BAJO"},
        organizacion="Ayuntamiento de Ejemplo",
    )


def test_el_alta_crea_organizacion_propietario_y_sistema(db):
    respuesta = registrar()

    assert respuesta.status_code == 201, respuesta.content
    tenant = Tenant.objects.get(nombre=ALTA["organizacion"])
    membresia = Membership.objects.get(tenant=tenant)
    assert membresia.role == Role.PROPIETARIO
    assert membresia.user.username == ALTA["email"]
    assert System.objects.filter(tenant=tenant).count() == 1
    # La contraseña vive en Cognito: en Django no hay ninguna que robar.
    assert not membresia.user.has_usable_password()
    assert UserIdentity.objects.get(email=ALTA["email"]).cognito_sub


def test_el_alta_reclama_la_categorizacion_hecha_sin_cuenta(db, informe_anonimo):
    respuesta = registrar(informe_token=str(informe_anonimo.token))

    assert respuesta.status_code == 201
    assert respuesta.json()["aviso"] == ""
    system = System.objects.get(pk=respuesta.json()["system_id"])
    niveles = {v.dim: v.nivel for v in DimensionValuation.objects.filter(system=system)}
    assert niveles == {"C": "MEDIO", "I": "MEDIO", "T": "BAJO", "A": "ALTO", "D": "BAJO"}
    assert system.categoria == "ALTA"
    informe_anonimo.refresh_from_db()
    assert informe_anonimo.system_id == system.pk
    # Deja de ser de un anónimo, así que deja de caducar.
    assert informe_anonimo.expira_en is None


def test_si_el_resultado_anonimo_caduco_el_alta_no_se_bloquea(db, informe_anonimo):
    InformeCategorizacion.objects.filter(pk=informe_anonimo.pk).update(
        expira_en=timezone.now() - timedelta(days=1)
    )

    respuesta = registrar(informe_token=str(informe_anonimo.token))

    assert respuesta.status_code == 201
    assert "caducado" in respuesta.json()["aviso"]
    system = System.objects.get(pk=respuesta.json()["system_id"])
    assert not DimensionValuation.objects.filter(system=system).exists()


def test_un_token_que_no_existe_tampoco_bloquea_el_alta(db):
    respuesta = registrar(informe_token="00000000-0000-0000-0000-000000000000")

    assert respuesta.status_code == 201
    assert "no hemos encontrado" in respuesta.json()["aviso"].lower()


def test_el_mismo_correo_no_se_registra_dos_veces(db):
    assert registrar().status_code == 201

    respuesta = registrar(organizacion="Otra cosa")

    assert respuesta.status_code == 400
    assert Tenant.objects.count() == 1


def test_un_alta_rota_a_mitad_no_deja_usuario_suelto_en_cognito(db, monkeypatch):
    """Si la transacción se cae, el usuario del pool se deshace.

    Un usuario en Cognito sin organización es alguien que no puede entrar y que nadie
    sabe que existe: el peor resultado posible de un alta.
    """

    def revienta(**kwargs):
        raise RuntimeError("la base de datos se cayó a mitad")

    monkeypatch.setattr(services, "_crear_estructura", revienta)

    with pytest.raises(RuntimeError):
        services.registrar_cuenta(
            email=ALTA["email"],
            password=ALTA["password"],
            organizacion=ALTA["organizacion"],
        )

    assert ALTA["email"] not in get_identity().cuentas
    assert not Tenant.objects.exists()
    assert not get_user_model().objects.filter(username=ALTA["email"]).exists()


def test_el_alta_queda_en_la_cadena_del_registro(db):
    registrar()

    tenant = Tenant.objects.get()
    entrada = AuditLog.objects.filter(tenant=tenant, accion="cuenta.alta").get()
    assert entrada.datos["email"] == ALTA["email"]
    assert AuditLog.verify_chain(tenant) == (True, None)


def test_una_contrasena_corta_la_rechaza_el_proveedor(db):
    respuesta = registrar(password="corta")

    assert respuesta.status_code == 422  # lo para el esquema antes de llegar al pool
    assert not Tenant.objects.exists()


def test_el_correo_se_normaliza(db):
    respuesta = registrar(email="  RSEG@Ayuntamiento.TEST ")

    assert respuesta.status_code == 201
    assert UserIdentity.objects.get().email == ALTA["email"]


def test_un_correo_con_mala_pinta_no_llega_al_proveedor(db):
    respuesta = registrar(email="esto-no-es-un-correo")

    assert respuesta.status_code == 400
    assert not get_identity().cuentas


def test_confirmar_el_correo_con_un_codigo_que_no_es(db):
    registrar()
    cliente = Client()

    respuesta = cliente.post(
        "/api/auth/confirm",
        data=json.dumps({"email": ALTA["email"], "codigo": "000000"}),
        content_type="application/json",
    )

    assert respuesta.status_code == 400
    with pytest.raises(IdentityError):
        get_identity().iniciar_sesion(ALTA["email"], ALTA["password"])
