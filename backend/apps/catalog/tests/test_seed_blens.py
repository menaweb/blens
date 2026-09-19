"""Carga de la capa propia: lo que BLENS añade al texto de la norma.

El seed es el activo principal del producto (§17), así que lo que se prueba es que entra
entero, que no entra si está mal y que volver a cargarlo deja lo mismo.
"""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.catalog.models import (
    EnsCheck,
    EvidenceTemplate,
    ProductEvidenceHint,
    ProfileBlock,
    ProfileOption,
    ProfileQuestion,
)


def test_se_cargan_las_dieciseis_familias(capa_blens):
    assert ProfileBlock.objects.filter(catalog=capa_blens).count() == 15
    assert ProfileQuestion.objects.filter(catalog=capa_blens).count() == 156
    assert ProfileOption.objects.filter(question__catalog=capa_blens).count() == 502
    assert EvidenceTemplate.objects.filter(catalog=capa_blens).count() == 199
    assert ProductEvidenceHint.objects.filter(catalog=capa_blens).count() == 34
    assert EnsCheck.objects.filter(catalog=capa_blens).count() == 459


def test_las_setenta_y_tres_medidas_tienen_alguna_evidencia_que_pedir(capa_blens):
    """Criterio de cierre de F4: ninguna medida se queda sin forma de demostrarse."""
    con_plantilla = set(
        EvidenceTemplate.objects.filter(catalog=capa_blens).values_list("measure__code", flat=True)
    )
    assert len(con_plantilla) == 73


def test_cada_check_se_ancla_al_requisito_literal_de_la_norma(capa_blens):
    """1 check = 1 item OSCAL: es lo que hace rastreable la verificación (§15)."""
    assert not EnsCheck.objects.filter(catalog=capa_blens, item__isnull=True).exists()
    check = EnsCheck.objects.get(catalog=capa_blens, code="CHK-op.exp.1.1")
    assert check.item.label == "op.exp.1.1"
    assert check.evidencia_esperada.exists()


def test_el_bloque_dice_lo_que_cuesta_sumando_sus_preguntas(capa_blens):
    bloque = ProfileBlock.objects.get(catalog=capa_blens, code="B04")
    minutos = sum(
        p.minutos_estimados
        for p in ProfileQuestion.objects.filter(catalog=capa_blens, bloque=bloque)
    )
    assert bloque.minutos_estimados == minutos > 0


def test_volver_a_cargarlo_deja_lo_mismo(capa_blens):
    antes = (
        ProfileQuestion.objects.filter(catalog=capa_blens).count(),
        EvidenceTemplate.objects.filter(catalog=capa_blens).count(),
        EnsCheck.objects.filter(catalog=capa_blens).count(),
    )
    call_command("seed_blens", verbosity=0)
    despues = (
        ProfileQuestion.objects.filter(catalog=capa_blens).count(),
        EvidenceTemplate.objects.filter(catalog=capa_blens).count(),
        EnsCheck.objects.filter(catalog=capa_blens).count(),
    )
    assert antes == despues


def test_sin_catalogo_importado_no_se_carga_nada(db):
    with pytest.raises(CommandError, match="import_ens_oscal"):
        call_command("seed_blens", verbosity=0)
