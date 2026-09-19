"""Export de la DdA a OSCAL. Modelo elegido: profile (ver `export.py`)."""

from engines.oscal_io.export import DecisionMedida, dda_to_oscal_profile

COMUN = dict(
    organizacion="Ayuntamiento de Ejemplo",
    sistema="Sede electrónica",
    version=2,
    categoria="MEDIA",
    niveles={"C": "MEDIO", "I": "MEDIO", "T": "BAJO", "A": "MEDIO", "D": "BAJO"},
    catalogo_href="https://www.boe.es/eli/es/rd/2022/05/03/311/con",
    catalogo_version="ENS-2022-OSCAL-1.0.0",
    fecha="2026-09-19T12:00:00+02:00",
)

DECISIONES = [
    DecisionMedida("org.1", True, motivo="categoría MEDIA"),
    DecisionMedida(
        "op.acc.5",
        True,
        refuerzos=("op.acc.5.r5",),
        selecciones={"op.acc.5.prm.rfz.medio": "op.acc.5.r2"},
    ),
    DecisionMedida("mp.info.4", False, justificacion="La trazabilidad no alcanza nivel ALTO"),
]


def perfil(**extra):
    return dda_to_oscal_profile(**{**COMUN, "decisiones": DECISIONES, **extra})["profile"]


def test_las_medidas_aplicables_van_en_include_y_las_demas_en_exclude():
    p = perfil()
    incluidos = p["imports"][0]["include-controls"][0]["with-ids"]
    excluidos = p["imports"][0]["exclude-controls"][0]["with-ids"]

    assert "org.1" in incluidos and "op.acc.5" in incluidos
    assert "mp.info.4" in excluidos
    assert set(incluidos).isdisjoint(excluidos)


def test_los_refuerzos_elegidos_viajan_como_controles_y_como_parametros():
    p = perfil()
    assert "op.acc.5.r5" in p["imports"][0]["include-controls"][0]["with-ids"]
    assert p["modify"]["set-parameters"] == [
        {"param-id": "op.acc.5.prm.rfz.medio", "values": ["op.acc.5.r2"]}
    ]


def test_la_justificacion_de_lo_excluido_no_se_pierde():
    assert "mp.info.4: La trazabilidad no alcanza nivel ALTO" in perfil()["imports"][0]["remarks"]


def test_la_categoria_y_los_niveles_van_en_las_props_del_ens():
    props = perfil()["metadata"]["props"]
    assert {"ns": "urn:es:ens", "name": "categoria", "value": "MEDIA"} in props
    assert {"ns": "urn:es:ens", "name": "nivel", "value": "BAJO", "class": "T"} in props


def test_es_determinista():
    """Mismo input, mismo fichero: un export se puede volver a generar y comparar."""
    assert perfil() == perfil()
    assert perfil()["uuid"] != perfil(version=3)["uuid"]


def test_sin_selecciones_no_hay_bloque_modify():
    p = dda_to_oscal_profile(**{**COMUN, "decisiones": [DecisionMedida("org.1", True)]})["profile"]
    assert "modify" not in p


def test_declara_la_version_de_oscal_y_el_catalogo_de_origen():
    p = perfil()
    assert p["metadata"]["oscal-version"] == "1.1.3"
    assert p["imports"][0]["href"] == COMUN["catalogo_href"]
