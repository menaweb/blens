"""El importador del catálogo OSCAL: carga, idempotencia y referencias huérfanas."""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.catalog.models import (
    CatalogVersion,
    EnsMeasure,
    EnsRefuerzo,
    EnsRequirementItem,
    EnsSelectionParam,
)


def test_carga_el_catalogo_completo(catalogo_importado):
    """Criterio de cierre de F1."""
    assert EnsMeasure.objects.filter(catalog=catalogo_importado).count() == 73
    assert EnsRefuerzo.objects.filter(measure__catalog=catalogo_importado).count() == 133
    # 467 items en el fichero, 5 de ellos aclaraciones del overview de mp.eq.4.
    assert EnsRequirementItem.objects.filter(catalog=catalogo_importado).count() == 462
    assert EnsSelectionParam.objects.filter(measure__catalog=catalogo_importado).count() == 10


def test_reimportar_no_duplica_nada(catalogo_importado, oscal_path):
    """Criterio de cierre de F1: el comando es idempotente."""
    call_command("import_ens_oscal", str(oscal_path))

    assert CatalogVersion.objects.count() == 1
    assert EnsMeasure.objects.count() == 73
    assert EnsRequirementItem.objects.count() == 462


def test_guarda_la_trazabilidad_de_la_fuente(catalogo_importado):
    assert len(catalogo_importado.source_sha256) == 64
    assert catalogo_importado.oscal_version.startswith("1.1")
    assert catalogo_importado.license == "EUPL-1.2"
    assert "boe.es" in catalogo_importado.source_url
    assert "meramente informativo" in catalogo_importado.remarks


def test_la_estructura_queda_bien_enlazada(catalogo_importado):
    medida = EnsMeasure.objects.get(catalog=catalogo_importado, code="op.acc.5")
    assert medida.familia == "op.acc" and medida.marco == "op"
    assert medida.refuerzos.count() == 7
    assert medida.params.count() == 3

    param = medida.params.get(nivel="MEDIO")
    assert param.choices == ["op.acc.5.r2", "op.acc.5.r3", "op.acc.5.r4"]

    # Los items de un refuerzo cuelgan del refuerzo, no solo de la medida.
    del_refuerzo = EnsRequirementItem.objects.filter(refuerzo__code="op.acc.5.r2")
    assert del_refuerzo.exists()
    assert all(i.measure.code == "op.acc.5" for i in del_refuerzo)


def test_los_items_anidados_conservan_su_padre(catalogo_importado):
    hijo = EnsRequirementItem.objects.get(catalog=catalogo_importado, code="mp.s.1.req.1")
    assert hijo.parent is not None
    assert hijo.parent.label == ""  # el item que agrupa no lleva numeración
    assert hijo.label == "mp.s.1.1"


def test_falla_si_una_version_nueva_deja_huerfana_la_capa_propia(db, oscal_modificado):
    """§15: una actualización de la norma no puede romper el seed en silencio."""

    def borrar_medida(datos):
        grupo = datos["catalog"]["groups"][0]  # org
        grupo["controls"] = [c for c in grupo["controls"] if c["id"] != "org.1"]

    with pytest.raises(CommandError) as error:
        call_command("import_ens_oscal", str(oscal_modificado(borrar_medida)))

    mensaje = str(error.value)
    assert "org.1" in mensaje
    assert "huérfanas" in mensaje
    assert CatalogVersion.objects.count() == 0  # no se importa nada a medias


def test_se_puede_forzar_el_import_saltando_la_comprobacion(db, oscal_modificado):
    def borrar_medida(datos):
        grupo = datos["catalog"]["groups"][0]
        grupo["controls"] = [c for c in grupo["controls"] if c["id"] != "org.1"]

    call_command("import_ens_oscal", str(oscal_modificado(borrar_medida)), "--skip-orphan-check")
    assert EnsMeasure.objects.count() == 72


def test_rechaza_un_catalogo_invalido(db, oscal_modificado):
    def romper(datos):
        datos["catalog"]["metadata"]["oscal-version"] = "3.0.0"

    with pytest.raises(CommandError) as error:
        call_command("import_ens_oscal", str(oscal_modificado(romper)))
    assert "OSCAL" in str(error.value)


def test_solo_una_version_vigente(catalogo_importado, oscal_path):
    call_command("import_ens_oscal", str(oscal_path), "--code", "ENS-2022-OSCAL-prueba")

    assert CatalogVersion.objects.count() == 2
    assert CatalogVersion.objects.filter(is_current=True).count() == 1
    assert CatalogVersion.current().code == "ENS-2022-OSCAL-prueba"
