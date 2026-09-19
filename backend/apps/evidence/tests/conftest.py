import pytest

from apps.compliance.models import System
from apps.compliance.services import guardar_valoracion


@pytest.fixture
def sistema(db, tenant, capa_blens):
    """Sistema MEDIA con su categorización hecha: es el punto donde empieza el perfilado."""
    sistema = System.objects.create(tenant=tenant, nombre="Sede electrónica")
    guardar_valoracion(
        sistema, {"C": "MEDIO", "I": "MEDIO", "T": "BAJO", "A": "MEDIO", "D": "MEDIO"}
    )
    sistema.refresh_from_db()
    return sistema


@pytest.fixture
def pregunta(capa_blens):
    """Busca una pregunta del catálogo por su código."""
    from apps.catalog.models import ProfileQuestion

    def _buscar(code: str) -> ProfileQuestion:
        return ProfileQuestion.objects.get(catalog=capa_blens, code=code)

    return _buscar
