"""El parser lee el catálogo oficial del Anexo II y rechaza lo que no lo es."""

import json

import pytest

from engines.oscal_io import load_catalog, parse_catalog
from engines.oscal_io.parser import OscalValidationError


def test_carga_las_73_medidas_y_los_133_refuerzos(catalogo):
    assert len(catalogo.measures) == 73
    assert len(catalogo.refuerzos) == 133


def test_los_requisitos_atomicos_son_462_de_los_467_items(catalogo):
    """467 son todos los `item` del fichero; 5 son aclaraciones del overview de mp.eq.4."""
    assert len(catalogo.items) == 462
    assert "Dispositivos multifunción" in catalogo.measure("mp.eq.4").overview


def test_las_etiquetas_de_los_items_no_son_unicas(catalogo):
    """Por eso un check se ancla al id del item, nunca al label suelto (§6)."""
    labels = [i.label for i in catalogo.items if i.label]
    assert len(labels) > len(set(labels))


def test_tres_marcos_y_dieciseis_familias(catalogo):
    assert sorted({m.marco for m in catalogo.measures}) == ["mp", "op", "org"]
    assert len({m.familia for m in catalogo.measures}) == 16
    assert catalogo.measure("org.1").familia == "org"  # org no tiene subfamilias
    assert catalogo.measure("op.exp.6").familia == "op.exp"


def test_41_refuerzos_sin_props_se_leen_como_opcionales(catalogo):
    """§3.1: pendiente de contrastar con las tablas del RD 311/2022."""
    assert sum(1 for r in catalogo.refuerzos if r.opcional) == 41
    assert catalogo.measure("org.2").refuerzos[0].opcional


def test_las_cuatro_medidas_con_seleccion_de_refuerzo(catalogo):
    con_seleccion = [m.id for m in catalogo.measures if m.params]
    assert con_seleccion == ["op.acc.5", "op.acc.6", "mp.com.4", "mp.s.2"]
    param = catalogo.measure("op.acc.5").params[0]
    assert param.how_many == "one"
    assert len(param.choices) == 4


def test_la_errata_de_mp_eq_2_no_afecta_a_la_aplicabilidad(catalogo):
    """El JSON la titula como mp.eq.1; el RD dice «Bloqueo de puesto de trabajo» (§3.1).

    Lo que usa BLENS son las props, y esas sí son correctas: Autenticidad MEDIO/ALTO.
    """
    aplicabilidad = catalogo.measure("mp.eq.2").aplicabilidad
    assert aplicabilidad.dimensiones == frozenset({"A"})
    assert aplicabilidad.niveles == frozenset({"MEDIO", "ALTO"})


def test_los_refuerzos_cuelgan_de_su_medida(catalogo):
    for refuerzo in catalogo.refuerzos:
        assert refuerzo.id.startswith(f"{refuerzo.measure_id}.r")


def test_el_sha256_identifica_el_fichero(catalogo_path):
    _, sha_uno = load_catalog(catalogo_path)
    _, sha_dos = load_catalog(catalogo_path)
    assert sha_uno == sha_dos and len(sha_uno) == 64


def test_metadatos_de_trazabilidad(catalogo):
    assert catalogo.oscal_version.startswith("1.1")
    assert catalogo.version == "1.0.0"
    assert "boe.es" in catalogo.source_url
    assert "carácter meramente informativo" in catalogo.remarks


# --- Lo que el parser debe rechazar ------------------------------------------


def test_rechaza_un_json_sin_catalogo():
    with pytest.raises(OscalValidationError):
        parse_catalog({"profile": {}})


def test_rechaza_una_version_de_oscal_distinta(catalogo_path):
    datos = json.loads(catalogo_path.read_text(encoding="utf-8"))
    datos["catalog"]["metadata"]["oscal-version"] = "2.0.0"
    with pytest.raises(OscalValidationError) as error:
        parse_catalog(datos)
    assert "versión OSCAL no soportada" in str(error.value)


def test_informa_de_todos_los_errores_a_la_vez(catalogo_path):
    datos = json.loads(catalogo_path.read_text(encoding="utf-8"))
    datos["catalog"]["metadata"]["oscal-version"] = "2.0.0"
    org = datos["catalog"]["groups"][0]["controls"][0]
    org["props"].append({"ns": "urn:es:ens", "name": "dimension", "value": "Inventada"})
    org["props"].append({"ns": "urn:es:ens", "name": "categoria", "value": "SUPREMA"})

    with pytest.raises(OscalValidationError) as error:
        parse_catalog(datos)
    assert len(error.value.errores) == 3
