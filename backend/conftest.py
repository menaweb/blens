"""Fixtures compartidas del backend."""

import pytest
from apps.compliance.models import System
from apps.tenancy.models import Membership, Role, Tenant
from django.contrib.auth import get_user_model


@pytest.fixture
def tenant(db):
    return Tenant.objects.create(nombre="Ayuntamiento de Ejemplo")


@pytest.fixture
def otro_tenant(db):
    return Tenant.objects.create(nombre="Otra Organización")


@pytest.fixture
def system(db, tenant):
    return System.objects.create(tenant=tenant, nombre="Sede electrónica", categoria="MEDIA")


@pytest.fixture
def usuarios(db):
    """Crea un usuario por rol para no repetirlo en cada test."""
    User = get_user_model()
    return {
        rol: User.objects.create_user(username=f"u_{rol.lower()}", password="x")
        for rol in Role.values
    }


@pytest.fixture
def miembro(db, tenant, usuarios):
    """Fábrica de membresías: `miembro(Role.TECNICO)` devuelve el usuario ya dado de alta."""

    def _crear(rol, *, systems=None, bloques=None, expires_at=None, estado="ACTIVA"):
        user = usuarios[rol]
        # Idempotente: llamarlo dos veces con el mismo rol en un test devuelve el mismo
        # usuario en lugar de chocar con unique(tenant, user).
        m, _ = Membership.objects.update_or_create(
            tenant=tenant,
            user=user,
            defaults={
                "role": rol,
                "bloques": bloques or [],
                "expires_at": expires_at,
                "estado": estado,
            },
        )
        m.systems.set(systems or [])
        return user

    return _crear


@pytest.fixture
def magerit(db):
    """Catálogo ENS importado + capa MAGERIT cargada (tipos, amenazas y salvaguardas).

    Carga el seed de verdad, no uno de juguete: el mapa medida↔amenaza es criterio propio
    de BLENS y lo que prueba el motor con él es el contrato con ese criterio.
    """
    from pathlib import Path

    from apps.catalog.models import CatalogVersion
    from django.core.management import call_command

    oscal = Path(__file__).resolve().parents[1] / "db/seed/oscal/ENS_Anexo_II_rev_9.json"
    call_command("import_ens_oscal", str(oscal), verbosity=0)
    call_command("seed_magerit", verbosity=0)
    return CatalogVersion.objects.get(is_current=True)
