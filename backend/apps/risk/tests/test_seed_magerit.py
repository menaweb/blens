"""El seed MAGERIT es dato, y el comando que lo carga es quien lo valida."""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.catalog.models import (
    EnsMeasure,
    MageritAssetType,
    MageritThreat,
    MaturityEffectiveness,
    MeasureThreatMap,
)


def test_carga_el_catalogo_completo(magerit):
    assert MageritThreat.objects.filter(catalog=magerit).count() == 50
    assert MageritAssetType.objects.filter(catalog=magerit, parent__isnull=True).count() == 10
    assert MeasureThreatMap.objects.filter(catalog=magerit).count() == 269


def test_las_73_medidas_frenan_algo(magerit):
    """§15: si una medida no aparece en el mapa, o falta en el seed o sobra en la norma."""
    citadas = set(
        MeasureThreatMap.objects.filter(catalog=magerit).values_list("measure__code", flat=True)
    )
    todas = set(EnsMeasure.objects.filter(catalog=magerit).values_list("code", flat=True))
    assert todas - citadas == set()


def test_ningun_peso_pasa_de_siete_decimas(magerit):
    """Ninguna medida sola anula una amenaza."""
    assert not MeasureThreatMap.objects.filter(catalog=magerit, weight__gt=0.7).exists()
    assert not MeasureThreatMap.objects.filter(catalog=magerit, weight__lte=0).exists()


def test_la_escala_de_eficacia_va_de_l0_a_l5(magerit):
    tabla = MaturityEffectiveness.tabla()
    assert sorted(tabla) == [0, 1, 2, 3, 4, 5]
    assert tabla[0] == 0
    assert tabla[5] == 1
    # Es la misma escala que el scoring, dividida entre cien: una sola fuente.
    from engines.scoring_engine import PORCENTAJE_POR_NIVEL

    for nivel, pct in PORCENTAJE_POR_NIVEL.items():
        assert tabla[nivel] * 100 == pct


def test_los_subtipos_heredan_el_caracter_terminal(magerit):
    datos = MageritAssetType.objects.get(catalog=magerit, code="D")
    assert datos.is_terminal
    assert all(sub.is_terminal for sub in datos.subtipos.all())
    hardware = MageritAssetType.objects.get(catalog=magerit, code="HW")
    assert not hardware.is_terminal


def test_es_idempotente(magerit):
    antes = MeasureThreatMap.objects.filter(catalog=magerit).count()
    call_command("seed_magerit", verbosity=0)
    assert MeasureThreatMap.objects.filter(catalog=magerit).count() == antes


def test_sin_catalogo_no_hay_seed(db):
    with pytest.raises(CommandError, match="import_ens_oscal"):
        call_command("seed_magerit", verbosity=0)


def test_anota_la_version_de_la_capa_propia(magerit):
    call_command("seed_magerit", "--layer-version", "lib-2026.1", verbosity=0)
    magerit.refresh_from_db()
    assert magerit.blens_layer_version == "lib-2026.1"
