"""Fixtures de los motores. Sin Django: los engines se prueban en aislamiento (§15)."""

from pathlib import Path

import pytest

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
