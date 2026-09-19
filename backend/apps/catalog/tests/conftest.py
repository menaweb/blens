import json
from pathlib import Path

import pytest
from django.core.management import call_command

OSCAL = Path(__file__).resolve().parents[4] / "db" / "seed" / "oscal" / "ENS_Anexo_II_rev_9.json"


@pytest.fixture
def oscal_path() -> Path:
    return OSCAL


@pytest.fixture
def catalogo_importado(db):
    call_command("import_ens_oscal", str(OSCAL))
    from apps.catalog.models import CatalogVersion

    return CatalogVersion.objects.get(is_current=True)


@pytest.fixture
def oscal_modificado(tmp_path):
    """Devuelve una función que escribe una copia del catálogo con algo cambiado."""

    def _escribir(transformar) -> Path:
        datos = json.loads(OSCAL.read_text(encoding="utf-8"))
        transformar(datos)
        destino = tmp_path / "catalogo.json"
        destino.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        return destino

    return _escribir
