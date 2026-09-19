"""Fixtures de los motores. Sin Django: los engines se prueban en aislamiento (§15)."""

from pathlib import Path

import pytest
import yaml

from engines.evidence_engine import bloques_desde, plantillas_desde, preguntas_desde
from engines.oscal_io import load_catalog

RAIZ = Path(__file__).resolve().parent.parent
OSCAL = RAIZ / "db" / "seed" / "oscal" / "ENS_Anexo_II_rev_9.json"


@pytest.fixture(scope="session")
def catalogo_path() -> Path:
    return OSCAL


@pytest.fixture(scope="session")
def catalogo():
    """El catálogo oficial de verdad, no uno de juguete: es el contrato con la norma."""
    catalogo, _ = load_catalog(OSCAL)
    return catalogo


SEED = RAIZ / "db" / "seed" / "blens"


def _documentos(patron: str) -> list[dict]:
    return [yaml.safe_load(ruta.read_text(encoding="utf-8")) for ruta in sorted(SEED.glob(patron))]


@pytest.fixture(scope="session")
def preguntas_seed():
    """El banco de preguntas real: 16 familias, tal y como se carga en el catálogo."""
    return tuple(p for doc in _documentos("questions.*.yaml") for p in preguntas_desde(doc))


@pytest.fixture(scope="session")
def plantillas_seed():
    """Las plantillas de evidencia reales. Son el activo principal del producto (§17)."""
    return tuple(
        t for doc in _documentos("evidence_templates.*.yaml") for t in plantillas_desde(doc)
    )


@pytest.fixture(scope="session")
def bloques_seed():
    """Los bloques del cuestionario: la unidad con la que se reparte el trabajo por rol."""
    return tuple(b for doc in _documentos("questions.*.yaml") for b in bloques_desde(doc))
