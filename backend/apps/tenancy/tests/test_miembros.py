"""Invitaciones y gestión de usuarios (M0).

Las reglas que se prueban aquí no son de Cognito: son de BLENS. Una invitación caduca,
una organización nunca se queda sin propietario, el acceso del auditor tiene fecha de
fin, y restablecer el segundo factor de otra persona deja rastro de quién lo hizo.
"""

import json
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from apps.tenancy.identity import get_identity
from apps.tenancy.models import (
    AuditLog,
    Invitation,
    Membership,
    MembershipEstado,
    Role,
    UserIdentity,
)
from apps.tenancy.testing import PASSWORD, como

NUEVA = "nueva@ayuntamiento.test"


def post(cliente, url, payload=None):
    return cliente.post(url, data=json.dumps(payload or {}), content_type="application/json")


def patch(cliente, url, payload):
    return cliente.patch(url, data=json.dumps(payload), content_type="application/json")


@pytest.fixture
def propietario(miembro):
    return miembro(Role.PROPIETARIO)


@pytest.fixture
def invitacion(db, tenant, propietario):
    """Invitación de técnico ya emitida, con su token en claro."""
    respuesta = post(
        como(propietario),
        "/api/members/invitations",
        {"email": NUEVA, "role": Role.TECNICO},
    )
    assert respuesta.status_code == 201, respuesta.content
    return respuesta.json()["enlace"].rsplit("/", 1)[-1]


# --- Emitir ---------------------------------------------------------------------


def test_el_propietario_invita_y_queda_pendiente(db, propietario, tenant):
    cliente = como(propietario)

    respuesta = post(cliente, "/api/members/invitations", {"email": NUEVA, "role": Role.TECNICO})

    assert respuesta.status_code == 201
    assert Invitation.objects.get(tenant=tenant).email == NUEVA
    pendientes = cliente.get("/api/members/invitations").json()
    assert [i["email"] for i in pendientes] == [NUEVA]


def test_el_tecnico_no_invita(db, miembro):
    respuesta = post(
        como(miembro(Role.TECNICO)),
        "/api/members/invitations",
        {"email": NUEVA, "role": Role.TECNICO},
    )

    assert respuesta.status_code == 403


def test_el_rseg_puede_dar_acceso_a_un_auditor_pero_no_fichar_tecnicos(db, miembro):
    cliente = como(miembro(Role.RSEG))

    auditor = post(
        cliente, "/api/members/invitations", {"email": "auditor@enac.test", "role": Role.AUDITOR}
    )
    tecnico = post(cliente, "/api/members/invitations", {"email": NUEVA, "role": Role.TECNICO})

    assert auditor.status_code == 201
    assert tecnico.status_code == 403


def test_el_acceso_del_auditor_nace_con_fecha_de_fin(db, propietario, tenant):
    emitida = post(
        como(propietario),
        "/api/members/invitations",
        {"email": "auditor@enac.test", "role": Role.AUDITOR},
    )
    token = emitida.json()["enlace"].rsplit("/", 1)[-1]

    Client().post(
        f"/api/auth/invitation/{token}/accept",
        data=json.dumps({"password": PASSWORD}),
        content_type="application/json",
    )

    membresia = Membership.objects.get(user__username="auditor@enac.test")
    assert membresia.expires_at is not None
    assert membresia.expires_at > timezone.now() + timedelta(days=80)


# --- Aceptar --------------------------------------------------------------------


def test_aceptar_una_invitacion_crea_la_cuenta_y_la_membresia(db, invitacion, tenant):
    respuesta = Client().post(
        f"/api/auth/invitation/{invitacion}/accept",
        data=json.dumps({"password": PASSWORD, "nombre": "Ana"}),
        content_type="application/json",
    )

    assert respuesta.status_code == 201
    membresia = Membership.objects.get(user__username=NUEVA)
    assert membresia.role == Role.TECNICO
    assert membresia.tenant == tenant
    assert UserIdentity.objects.get(email=NUEVA).nombre == "Ana"
    assert NUEVA in get_identity().cuentas
    assert Invitation.objects.get(email=NUEVA).used_at is not None


def test_ver_la_invitacion_dice_quien_invita_y_a_que(db, invitacion, tenant):
    datos = Client().get(f"/api/auth/invitation/{invitacion}").json()

    assert datos["organizacion"] == tenant.nombre
    assert datos["role_nombre"] == "Técnico"
    assert datos["tiene_cuenta"] is False


def test_una_invitacion_usada_no_sirve_dos_veces(db, invitacion):
    cuerpo = json.dumps({"password": PASSWORD})
    primera = Client().post(
        f"/api/auth/invitation/{invitacion}/accept", data=cuerpo, content_type="application/json"
    )
    assert primera.status_code == 201

    segunda = Client().post(
        f"/api/auth/invitation/{invitacion}/accept", data=cuerpo, content_type="application/json"
    )

    assert segunda.status_code == 410
    assert Membership.objects.filter(user__username=NUEVA).count() == 1


def test_una_invitacion_caducada_no_crea_nada_ni_en_cognito(db, invitacion):
    Invitation.objects.filter(email=NUEVA).update(expires_at=timezone.now() - timedelta(hours=1))

    respuesta = Client().post(
        f"/api/auth/invitation/{invitacion}/accept",
        data=json.dumps({"password": PASSWORD}),
        content_type="application/json",
    )

    assert respuesta.status_code == 410
    assert not Membership.objects.filter(user__username=NUEVA).exists()
    assert NUEVA not in get_identity().cuentas
    assert not get_user_model().objects.filter(username=NUEVA).exists()


def test_una_invitacion_revocada_deja_de_existir(db, invitacion, propietario):
    cliente = como(propietario)
    pendiente = cliente.get("/api/members/invitations").json()[0]

    borrada = cliente.delete(f"/api/members/invitations/{pendiente['id']}")

    assert borrada.status_code == 204
    respuesta = Client().get(f"/api/auth/invitation/{invitacion}")
    assert respuesta.status_code == 410


def test_quien_ya_tiene_cuenta_no_repite_contrasena(db, tenant, propietario, miembro, usuarios):
    """Una identidad, varias membresías: el consultor que trabaja con dos clientes."""
    otro = usuarios[Role.CONSULTOR]
    emitida = post(
        como(propietario),
        "/api/members/invitations",
        {"email": otro.username, "role": Role.CONSULTOR},
    )
    token = emitida.json()["enlace"].rsplit("/", 1)[-1]

    respuesta = Client().post(
        f"/api/auth/invitation/{token}/accept",
        data=json.dumps({}),
        content_type="application/json",
    )

    assert respuesta.status_code == 201
    assert Membership.objects.filter(user=otro, tenant=tenant).exists()
    assert UserIdentity.objects.filter(user=otro).count() == 1


# --- Gestionar ------------------------------------------------------------------


def test_cambiar_el_rol_de_alguien(db, propietario, miembro):
    tecnico = miembro(Role.TECNICO)
    membresia = Membership.objects.get(user=tecnico)

    respuesta = patch(como(propietario), f"/api/members/{membresia.pk}", {"role": Role.RSEG})

    assert respuesta.status_code == 200
    assert Membership.objects.get(pk=membresia.pk).role == Role.RSEG


def test_la_ultima_propietaria_no_puede_degradarse(db, propietario):
    membresia = Membership.objects.get(user=propietario)

    respuesta = patch(como(propietario), f"/api/members/{membresia.pk}", {"role": Role.TECNICO})

    assert respuesta.status_code == 409
    assert "propietaria" in respuesta.json()["detail"]
    assert Membership.objects.get(pk=membresia.pk).role == Role.PROPIETARIO


def test_la_ultima_propietaria_no_puede_revocarse(db, propietario):
    membresia = Membership.objects.get(user=propietario)

    respuesta = post(como(propietario), f"/api/members/{membresia.pk}/revoke")

    assert respuesta.status_code == 409
    assert Membership.objects.get(pk=membresia.pk).estado == MembershipEstado.ACTIVA


def test_transferir_la_propiedad_deja_a_quien_transfiere_como_rseg(db, propietario, miembro):
    tecnico = miembro(Role.TECNICO)
    destino = Membership.objects.get(user=tecnico)

    respuesta = post(como(propietario), f"/api/members/{destino.pk}/transfer-ownership")

    assert respuesta.status_code == 200
    assert Membership.objects.get(pk=destino.pk).role == Role.PROPIETARIO
    assert Membership.objects.get(user=propietario).role == Role.RSEG


def test_revocar_a_alguien_le_quita_el_acceso_de_verdad(db, propietario, miembro):
    tecnico = miembro(Role.TECNICO)
    cliente_tecnico = como(tecnico)
    assert cliente_tecnico.get("/api/systems").status_code == 200

    post(como(propietario), f"/api/members/{Membership.objects.get(user=tecnico).pk}/revoke")

    assert cliente_tecnico.get("/api/systems").status_code == 403


def test_restablecer_el_segundo_factor_queda_registrado(db, propietario, miembro, tenant):
    rseg = miembro(Role.RSEG)
    get_identity().cuentas[rseg.username].mfa_activo = True
    membresia = Membership.objects.get(user=rseg)

    respuesta = post(como(propietario), f"/api/members/{membresia.pk}/reset-mfa")

    assert respuesta.status_code == 200
    assert get_identity().cuentas[rseg.username].mfa_activo is False
    assert UserIdentity.objects.get(user=rseg).mfa_activado is False
    entrada = AuditLog.objects.filter(accion="miembro.restablecer_mfa").get()
    assert entrada.user == propietario
    assert entrada.datos["usuario"] == rseg.username
    assert AuditLog.verify_chain(tenant) == (True, None)


def test_mi_actividad_solo_muestra_lo_mio(db, propietario, miembro):
    tecnico = miembro(Role.TECNICO)
    post(como(propietario), "/api/members/invitations", {"email": NUEVA, "role": Role.TECNICO})

    mia = como(propietario).get("/api/me/activity").json()
    ajena = como(tecnico).get("/api/me/activity").json()

    assert any(e["accion"] == "miembro.invitar" for e in mia)
    assert ajena == []
