"""Invitaciones: el token no se guarda en claro y el auditor caduca obligatoriamente."""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.tenancy.models import Invitation, Membership, Role


@pytest.mark.django_db
def test_el_token_solo_se_guarda_hasheado(tenant):
    inv, token = Invitation.issue(tenant=tenant, email="rseg@ejemplo.es", role=Role.RSEG)
    assert token not in (inv.token_hash, "")
    assert inv.token_hash == Invitation.hash_token(token)
    assert inv.vigente


@pytest.mark.django_db
def test_la_invitacion_caduca(tenant):
    inv, _ = Invitation.issue(tenant=tenant, email="a@ejemplo.es", role=Role.TECNICO, dias=0)
    inv.expires_at = timezone.now() - timedelta(minutes=1)
    assert not inv.vigente


@pytest.mark.django_db
def test_la_membresia_de_auditor_exige_caducidad(tenant, usuarios):
    m = Membership(tenant=tenant, user=usuarios[Role.AUDITOR], role=Role.AUDITOR)
    with pytest.raises(ValidationError):
        m.clean()

    m.expires_at = timezone.now() + timedelta(days=15)
    m.clean()  # no levanta
