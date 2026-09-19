"""Registro de actividad: append-only con hash encadenado (op.exp.8/9)."""

import pytest

from apps.tenancy.models import AuditLog


@pytest.mark.django_db
def test_la_cadena_enlaza_cada_entrada_con_la_anterior(tenant):
    a = AuditLog.append(accion="dda.aprobar", tenant=tenant)
    b = AuditLog.append(accion="evidencia.validar", tenant=tenant)
    assert a.prev_hash == ""
    assert b.prev_hash == a.hash
    assert AuditLog.verify_chain(tenant) == (True, None)


@pytest.mark.django_db
def test_manipular_una_entrada_rompe_la_cadena(tenant):
    AuditLog.append(accion="dda.aprobar", tenant=tenant)
    manipulada = AuditLog.append(accion="evidencia.validar", tenant=tenant)
    AuditLog.append(accion="documento.aprobar", tenant=tenant)

    AuditLog.objects.filter(pk=manipulada.pk).update(accion="evidencia.rechazar")

    integra, rota_en = AuditLog.verify_chain(tenant)
    assert not integra
    assert rota_en == manipulada.pk


@pytest.mark.django_db
def test_cada_organizacion_tiene_su_propia_cadena(tenant, otro_tenant):
    a = AuditLog.append(accion="dda.aprobar", tenant=tenant)
    b = AuditLog.append(accion="dda.aprobar", tenant=otro_tenant)
    assert b.prev_hash == ""  # no se engancha a la cadena del otro cliente
    assert a.hash != b.hash
    assert AuditLog.verify_chain(tenant) == (True, None)
    assert AuditLog.verify_chain(otro_tenant) == (True, None)


@pytest.mark.django_db
def test_registra_el_objeto_afectado(tenant, system):
    entrada = AuditLog.append(accion="madurez.editar", tenant=tenant, objeto=system)
    assert entrada.objeto_tipo == "System"
    assert entrada.objeto_id == str(system.pk)
