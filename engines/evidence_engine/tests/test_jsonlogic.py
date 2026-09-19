"""El subconjunto de JSON Logic con el que están escritas las reglas del seed.

Lo que se fija aquí es **semántica de producto**, no trivia del lenguaje: qué pasa cuando
falta un hecho, y qué significa un hecho con varios valores. De eso depende qué evidencias
se le piden a un cliente.
"""

import pytest

from engines.evidence_engine import ReglaInvalida, evaluar, hechos_citados, variables_citadas

DATOS = {
    "categoria_orden": 2,
    "nivel_orden": {"C": 2, "D": 3},
    "hechos": {
        "inventario": "excel",
        "cpd_acceso": ["tarjeta", "llave"],
        "sbom": False,
        "equipos_total": 60,
    },
}


def test_var_recorre_rutas_con_puntos():
    assert evaluar({"var": "hechos.inventario"}, DATOS) == "excel"
    assert evaluar({"var": "nivel_orden.D"}, DATOS) == 3


def test_var_de_lo_que_no_existe_es_nulo_y_admite_valor_por_defecto():
    assert evaluar({"var": "hechos.no_preguntado"}, DATOS) is None
    assert evaluar({"var": ["hechos.no_preguntado", "vacío"]}, DATOS) == "vacío"


def test_sin_regla_todo_se_cumple():
    assert evaluar(None, DATOS) is True


def test_comparaciones_con_lo_que_falta_son_falsas_nunca_una_excepcion():
    assert evaluar({">=": [{"var": "hechos.no_preguntado"}, 1]}, DATOS) is False
    assert evaluar({"in": [{"var": "hechos.no_preguntado"}, ["a"]]}, DATOS) is False
    assert evaluar({"==": [{"var": "hechos.no_preguntado"}, "a"]}, DATOS) is False


def test_los_booleanos_no_son_unos_ni_ceros():
    assert evaluar({"==": [{"var": "hechos.sbom"}, False]}, DATOS) is True
    assert evaluar({"==": [{"var": "hechos.sbom"}, 0]}, DATOS) is False


def test_in_mira_dentro_de_listas_y_de_cadenas():
    assert evaluar({"in": [{"var": "hechos.inventario"}, ["excel", "herramienta"]]}, DATOS) is True
    assert evaluar({"in": ["xce", {"var": "hechos.inventario"}]}, DATOS) is True


def test_un_hecho_con_varios_valores_se_compara_como_conjunto():
    """Marcar tarjeta **y** llave tiene que pedir las evidencias de las dos cosas."""
    assert evaluar({"==": [{"var": "hechos.cpd_acceso"}, "llave"]}, DATOS) is True
    assert evaluar({"in": [{"var": "hechos.cpd_acceso"}, ["tarjeta", "biometria"]]}, DATOS) is True
    assert evaluar({"in": ["llave", {"var": "hechos.cpd_acceso"}]}, DATOS) is True


def test_distinto_de_un_hecho_multiple_es_que_ninguno_coincide():
    assert evaluar({"!=": [{"var": "hechos.cpd_acceso"}, "llave"]}, DATOS) is False
    assert evaluar({"!=": [{"var": "hechos.cpd_acceso"}, "biometria"]}, DATOS) is True


def test_and_y_or_cortocircuitan():
    regla = {"and": [{">=": [{"var": "categoria_orden"}, 3]}, {"var": "revienta.si.se.evalua"}]}
    assert evaluar(regla, DATOS) is False
    assert evaluar({"or": [{">=": [{"var": "categoria_orden"}, 2]}, False]}, DATOS) is True


def test_un_operador_desconocido_revienta_en_lugar_de_valer_falso():
    """Una errata en el seed tiene que parar la carga, no cambiar la carpeta en silencio."""
    with pytest.raises(ReglaInvalida):
        evaluar({"cat": ["a", "b"]}, DATOS)
    with pytest.raises(ReglaInvalida):
        evaluar({"==": [1, 1], "!=": [1, 2]}, DATOS)


def test_se_puede_saber_de_que_depende_una_regla_sin_evaluarla():
    regla = {
        "and": [
            {">=": [{"var": "nivel_orden.CITA"}, 2]},
            {"in": [{"var": "hechos.inventario"}, ["excel"]]},
        ]
    }
    assert variables_citadas(regla) == {"nivel_orden.CITA", "hechos.inventario"}
    assert hechos_citados(regla) == {"inventario"}


# --- el resto del subconjunto: no lo usa el seed de hoy, pero lo admite el evaluador ----


def test_negacion_y_condicional():
    assert evaluar({"!": [{"var": "hechos.sbom"}]}, DATOS) is True
    assert evaluar({"!!": [{"var": "hechos.inventario"}]}, DATOS) is True
    assert evaluar({"if": [{"var": "hechos.sbom"}, "con", "sin"]}, DATOS) == "sin"
    assert evaluar({"if": [True, "con", "sin"]}, DATOS) == "con"
    assert evaluar({"if": [False]}, DATOS) is False
    assert evaluar({"if": []}, DATOS) is None


def test_las_cuatro_comparaciones_numericas():
    assert evaluar({">": [{"var": "hechos.equipos_total"}, 10]}, DATOS) is True
    assert evaluar({"<": [{"var": "hechos.equipos_total"}, 10]}, DATOS) is False
    assert evaluar({"<=": [{"var": "hechos.equipos_total"}, 60]}, DATOS) is True
    assert evaluar({">=": [{"var": "hechos.equipos_total"}, 61]}, DATOS) is False
    assert evaluar({">": [{"var": "hechos.equipos_total"}, 60]}, DATOS) is False
    assert evaluar({"<=": [{"var": "hechos.equipos_total"}, 59]}, DATOS) is False
    # Comparar textos no lanza: es falso, porque un texto no es una cantidad.
    assert evaluar({">": [{"var": "hechos.inventario"}, 1]}, DATOS) is False


def test_and_con_todo_cierto_devuelve_lo_ultimo():
    assert evaluar({"and": [True, {"var": "hechos.inventario"}]}, DATOS) == "excel"


def test_or_con_todo_falso_vale_falso():
    assert evaluar({"or": [False, {">=": [{"var": "categoria_orden"}, 9]}]}, DATOS) is False


def test_var_vacio_devuelve_el_contexto_entero():
    assert evaluar({"var": ""}, DATOS) is DATOS


def test_una_ruta_que_no_es_texto_es_una_regla_invalida():
    with pytest.raises(ReglaInvalida):
        evaluar({"var": {"vuelta": "de tuerca"}}, DATOS)


def test_bajar_por_una_ruta_que_no_lleva_a_ningun_sitio():
    assert evaluar({"var": "hechos.inventario.mas.alla"}, DATOS) is None


def test_in_con_varios_valores_contra_un_texto_y_contra_lo_que_no_es_coleccion():
    assert evaluar({"in": [{"var": "hechos.cpd_acceso"}, "solo con tarjeta"]}, DATOS) is True
    assert evaluar({"in": ["a", 42]}, DATOS) is False
