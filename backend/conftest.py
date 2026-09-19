"""Fixtures compartidas del backend.

La autenticación va por token de Cognito (D1), y en los tests el proveedor es el doble
en memoria de `apps.tenancy.identity`: **la suite no llama a AWS**. Por eso cada usuario
de prueba nace con su identidad y `como(usuario)` devuelve un cliente ya autenticado con
un token de verdad, emitido por el mismo camino que usaría una persona.
"""

import pytest
from apps.compliance.models import System
from apps.tenancy.identity import get_identity, reset_identity
from apps.tenancy.models import Membership, Role, Tenant, UserIdentity
from apps.tenancy.testing import PASSWORD
from django.contrib.auth import get_user_model
from django.test import Client


@pytest.fixture(autouse=True)
def identidad_en_memoria(settings):
    """Fuerza el doble del proveedor de identidad y lo vacía entre tests."""
    settings.COGNITO = {**settings.COGNITO, "FAKE": True}
    reset_identity()
    yield
    reset_identity()


@pytest.fixture
def tenant(db):
    return Tenant.objects.create(nombre="Ayuntamiento de Ejemplo")


@pytest.fixture
def otro_tenant(db):
    return Tenant.objects.create(nombre="Otra Organización")


@pytest.fixture
def catalogo(db):
    """Catálogo ENS importado del OSCAL oficial. Lo necesita todo lo que categoriza."""
    from pathlib import Path

    from apps.catalog.models import CatalogVersion
    from django.core.management import call_command

    oscal = Path(__file__).resolve().parents[1] / "db/seed/oscal/ENS_Anexo_II_rev_9.json"
    call_command("import_ens_oscal", str(oscal), verbosity=0)
    return CatalogVersion.objects.get(is_current=True)


@pytest.fixture
def system(db, tenant):
    return System.objects.create(tenant=tenant, nombre="Sede electrónica", categoria="MEDIA")


@pytest.fixture
def usuarios(db):
    """Un usuario por rol, cada uno con su identidad en el proveedor.

    Nacen con el segundo factor ya activado: son cuentas en uso, no recién creadas. Los
    tests que prueban el MFA lo desactivan a propósito.
    """
    User = get_user_model()
    identidad = get_identity()
    creados = {}
    for rol in Role.values:
        email = f"{rol.lower()}@ejemplo.test"
        user = User.objects.create_user(username=email, email=email, password=None)
        user.set_unusable_password()
        user.save()
        sub = identidad.registrar(email, PASSWORD)
        identidad.confirmar_registro(email, "123456")
        UserIdentity.objects.create(user=user, cognito_sub=sub, email=email, mfa_activado=True)
        creados[rol] = user
    return creados


@pytest.fixture
def anonimo(db):
    """Cliente sin credenciales, para comprobar que un endpoint no responde sin sesión."""
    return Client()


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


@pytest.fixture
def capa_blens(db):
    """Catálogo ENS + capa propia: checks, preguntas de perfilado y plantillas de evidencia.

    El seed de verdad, igual que en `magerit`: lo que prueban los tests de perfilado y de
    evidencias es el contenido tanto como el código, porque el contenido es el producto.
    """
    from pathlib import Path

    from apps.catalog.models import CatalogVersion
    from django.core.management import call_command

    oscal = Path(__file__).resolve().parents[1] / "db/seed/oscal/ENS_Anexo_II_rev_9.json"
    call_command("import_ens_oscal", str(oscal), verbosity=0)
    call_command("seed_blens", verbosity=0)
    return CatalogVersion.objects.get(is_current=True)
