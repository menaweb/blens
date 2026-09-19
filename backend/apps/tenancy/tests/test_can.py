"""Permisos: la matriz de `docs/roles_y_permisos.md` §3 y la separación de funciones.

Los objetos de prueba son `SimpleNamespace` a propósito: `can()` trabaja con atributos
(`tenant_id`, `system_id`, `bloque`, autoría), no con modelos concretos, así que estos
tests siguen valiendo cuando en F4/F5 existan de verdad `Evidencia` y `DocumentoVersion`.
"""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from apps.tenancy.models import Role
from apps.tenancy.permissions import can, require


def evidencia(tenant, *, aportada_por=None, system=None, bloque=None, excepcion=False):
    return SimpleNamespace(
        tenant_id=tenant.pk,
        system_id=getattr(system, "pk", None),
        aportada_por_id=getattr(aportada_por, "pk", None),
        bloque=bloque,
        excepcion_separacion=excepcion,
    )


def documento(tenant, *, autor=None):
    return SimpleNamespace(tenant_id=tenant.pk, autor_id=getattr(autor, "pk", None))


# --- Criterios de cierre de F0 -------------------------------------------------


def test_tecnico_no_valida_evidencias(tenant, miembro):
    tecnico = miembro(Role.TECNICO)
    assert can(tecnico, "evidencia.aportar", evidencia(tenant))
    assert not can(tecnico, "evidencia.validar", evidencia(tenant))


def test_tecnico_no_aprueba_documentos(tenant, miembro):
    tecnico = miembro(Role.TECNICO)
    assert can(tecnico, "documento.redactar", documento(tenant))
    assert not can(tecnico, "documento.aprobar", documento(tenant))


def test_quien_sube_una_evidencia_no_la_valida_aunque_sea_rseg(tenant, miembro):
    rseg = miembro(Role.RSEG)
    assert can(rseg, "evidencia.validar", evidencia(tenant))  # la de otro, sí
    assert not can(rseg, "evidencia.validar", evidencia(tenant, aportada_por=rseg))


def test_quien_redacta_un_documento_no_lo_aprueba(tenant, miembro):
    rseg = miembro(Role.RSEG)
    assert not can(rseg, "documento.aprobar", documento(tenant, autor=rseg))


def test_excepcion_justificada_permite_autovalidar(tenant, miembro):
    """Organización demasiado pequeña para separar: la excepción queda registrada."""
    rseg = miembro(Role.RSEG)
    propia = evidencia(tenant, aportada_por=rseg, excepcion=True)
    assert can(rseg, "evidencia.validar", propia)


# --- Matriz --------------------------------------------------------------------


def test_solo_el_rseg_aprueba_la_dda(tenant, miembro):
    assert can(miembro(Role.RSEG), "dda.aprobar", SimpleNamespace(tenant_id=tenant.pk))
    assert not can(miembro(Role.PROPIETARIO), "dda.aprobar", SimpleNamespace(tenant_id=tenant.pk))


def test_el_tecnico_no_acepta_riesgo_residual(tenant, miembro):
    riesgo = SimpleNamespace(tenant_id=tenant.pk)
    assert can(miembro(Role.TECNICO), "riesgo.editar", riesgo)
    assert not can(miembro(Role.TECNICO), "riesgo.aceptar", riesgo)
    assert can(miembro(Role.DIRECCION), "riesgo.aceptar", riesgo)


def test_direccion_solo_lee(tenant, miembro):
    direccion = miembro(Role.DIRECCION)
    obj = SimpleNamespace(tenant_id=tenant.pk)
    assert can(direccion, "madurez.leer", obj)
    assert not can(direccion, "madurez.editar", obj)


def test_auditor_no_toca_nada(tenant, miembro):
    auditor = miembro(Role.AUDITOR, expires_at=timezone.now() + timedelta(days=30))
    assert can(auditor, "paquete.leer", SimpleNamespace(tenant_id=tenant.pk))
    assert not can(auditor, "paquete.generar", SimpleNamespace(tenant_id=tenant.pk))
    assert not can(auditor, "evidencia.aportar", evidencia(tenant))
    assert not can(auditor, "usuarios.leer", SimpleNamespace(tenant_id=tenant.pk))


def test_el_catalogo_es_solo_lectura_para_todos(tenant, miembro):
    for rol in (Role.PROPIETARIO, Role.RSEG, Role.TECNICO, Role.COLABORADOR, Role.DIRECCION):
        assert can(miembro(rol), "catalogo.leer", SimpleNamespace(tenant_id=tenant.pk))


def test_solo_el_propietario_factura_y_borra(tenant, miembro):
    assert can(miembro(Role.PROPIETARIO), "facturacion.gestionar", tenant)
    assert not can(miembro(Role.RSEG), "facturacion.gestionar", tenant)
    assert not can(miembro(Role.RSEG), "tenant.borrar", tenant)


# --- Ámbito y estado de la membresía -------------------------------------------


def test_sin_membresia_no_hay_permiso(tenant, usuarios):
    forastero = usuarios[Role.TECNICO]
    assert not can(forastero, "perfilado.leer", SimpleNamespace(tenant_id=tenant.pk))


def test_membresia_caducada_no_vale(tenant, miembro):
    auditor = miembro(Role.AUDITOR, expires_at=timezone.now() - timedelta(days=1))
    assert not can(auditor, "paquete.leer", SimpleNamespace(tenant_id=tenant.pk))


def test_membresia_revocada_no_vale(tenant, miembro):
    tecnico = miembro(Role.TECNICO, estado="REVOCADA")
    assert not can(tecnico, "perfilado.responder", SimpleNamespace(tenant_id=tenant.pk))


def test_ambito_por_sistema(db, tenant, miembro, system):
    from apps.compliance.models import System

    otro = System.objects.create(tenant=tenant, nombre="Intranet")
    tecnico = miembro(Role.TECNICO, systems=[system])
    assert can(tecnico, "madurez.editar", SimpleNamespace(tenant_id=tenant.pk, system_id=system.pk))
    assert not can(
        tecnico, "madurez.editar", SimpleNamespace(tenant_id=tenant.pk, system_id=otro.pk)
    )


def test_colaborador_solo_ve_sus_bloques(tenant, miembro):
    colaborador = miembro(Role.COLABORADOR, bloques=["B17"])
    assert can(
        colaborador, "perfilado.responder", SimpleNamespace(tenant_id=tenant.pk, bloque="B17")
    )
    assert not can(
        colaborador, "perfilado.responder", SimpleNamespace(tenant_id=tenant.pk, bloque="B04")
    )
    assert not can(colaborador, "dda.leer", SimpleNamespace(tenant_id=tenant.pk))


def test_el_superusuario_no_salta_los_permisos(db, tenant):
    """El soporte de BLENS entra con consentimiento y traza, no con un interruptor (§5)."""
    from django.contrib.auth import get_user_model

    root = get_user_model().objects.create_superuser("root", "root@example.com", "x")
    assert not can(root, "paquete.leer", SimpleNamespace(tenant_id=tenant.pk))


# --- API de la función ---------------------------------------------------------


def test_accion_desconocida_es_un_error_de_programacion(tenant, miembro):
    with pytest.raises(ValueError):
        can(miembro(Role.RSEG), "inventada.accion", SimpleNamespace(tenant_id=tenant.pk))


def test_require_levanta_permission_denied(tenant, miembro):
    with pytest.raises(PermissionDenied):
        require(miembro(Role.TECNICO), "evidencia.validar", evidencia(tenant))
