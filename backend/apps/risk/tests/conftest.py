import pytest

from apps.compliance.models import System
from apps.compliance.services import asegurar_valoraciones, guardar_valoracion
from apps.risk.models import Asset, AssetDependency, AssetValuation
from apps.tenancy.models import Role


@pytest.fixture
def sistema(db, tenant, magerit):
    system = System.objects.create(tenant=tenant, nombre="Sede electrónica")
    guardar_valoracion(system, {"C": "MEDIO", "I": "MEDIO", "T": "BAJO", "A": "MEDIO", "D": "ALTO"})
    system.refresh_from_db()
    asegurar_valoraciones(system)
    return system


@pytest.fixture
def tipo(magerit):
    """Devuelve el tipo de activo por su código MAGERIT."""
    from apps.catalog.models import MageritAssetType

    def _tipo(code):
        return MageritAssetType.objects.get(catalog=magerit, code=code)

    return _tipo


@pytest.fixture
def sede_y_servidor(sistema, tipo):
    """El caso de §9.3: un servicio que vale 9 en D y el servidor que lo sostiene."""
    sede = Asset.objects.create(
        tenant=sistema.tenant, system=sistema, asset_type=tipo("S"), nombre="Sede electrónica"
    )
    AssetValuation.objects.create(asset=sede, dim="D", own_value=9)
    servidor = Asset.objects.create(
        tenant=sistema.tenant, system=sistema, asset_type=tipo("HW"), nombre="Servidor web"
    )
    AssetDependency.objects.create(parent=sede, child=servidor, degree=1)
    return sede, servidor


@pytest.fixture
def tecnico(miembro):
    return miembro(Role.TECNICO)


@pytest.fixture
def rseg(miembro):
    return miembro(Role.RSEG)


@pytest.fixture(autouse=True)
def celery_sincrono(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
