"""El motor de evidencias con un cuestionario de juguete: qué se pregunta, qué hechos deja
una respuesta y qué evidencias salen de ahí.

El seed de verdad se prueba aparte (`test_seed.py`). Aquí se fija el comportamiento.
"""

import pytest

from engines.evidence_engine import (
    Campo,
    Opcion,
    Plantilla,
    Pregunta,
    contexto_de_datos,
    derivar_requisitos,
    hechos_de_respuesta,
    preguntas_visibles,
    reconciliar,
    se_cumple,
)


@pytest.fixture
def cuestionario():
    return (
        Pregunta(
            code="mp.if.areas",
            bloque="B03",
            orden=10,
            tipo="MULTI",
            texto="¿Dónde están los equipos?",
            opciones=(
                Opcion("cpd", "CPD propio", {"instalacion_cpd": True}),
                Opcion("proveedor", "En un proveedor", {"instalacion_externa": True}),
            ),
        ),
        Pregunta(
            code="mp.if.acceso",
            bloque="B03",
            orden=20,
            tipo="MULTI",
            texto="¿Cómo se entra al CPD?",
            show_if={"==": [{"var": "hechos.instalacion_cpd"}, True]},
            opciones=(
                Opcion("tarjeta", "Tarjeta", {"cpd_acceso": "tarjeta"}),
                Opcion("llave", "Llave", {"cpd_acceso": "llave"}),
            ),
        ),
    )


def contexto(**hechos):
    return contexto_de_datos(
        categoria="MEDIA",
        niveles={"C": "MEDIO", "I": "MEDIO", "T": "BAJO", "A": "MEDIO", "D": "ALTO"},
        hechos=hechos,
        origen={clave: "mp.if.areas" for clave in hechos},
    )


# --- qué se pregunta ---------------------------------------------------------------


def test_una_pregunta_de_seguimiento_no_aparece_hasta_que_se_responde_la_suya(cuestionario):
    """Sin el hecho no hay condición: si no se sabe, no se enseña (§10bis.3)."""
    assert [p.code for p in preguntas_visibles(cuestionario, contexto())] == ["mp.if.areas"]

    con_cpd = contexto(instalacion_cpd=True)
    assert [p.code for p in preguntas_visibles(cuestionario, con_cpd)] == [
        "mp.if.areas",
        "mp.if.acceso",
    ]


def test_la_pregunta_de_seguimiento_desaparece_si_la_respuesta_ya_no_la_justifica(cuestionario):
    sin_cpd = contexto(instalacion_externa=True)
    assert [p.code for p in preguntas_visibles(cuestionario, sin_cpd)] == ["mp.if.areas"]


def test_las_reglas_leen_el_nivel_mas_alto_del_conjunto_de_dimensiones():
    ctx = contexto()
    assert se_cumple({">=": [{"var": "nivel_orden.D"}, 3]}, ctx) is True
    assert se_cumple({">=": [{"var": "nivel_orden.T"}, 2]}, ctx) is False
    # CITA incluye T (BAJO) pero también C, I y A (MEDIO): manda el más alto.
    assert se_cumple({">=": [{"var": "nivel_orden.CITA"}, 2]}, ctx) is True
    assert se_cumple({">=": [{"var": "categoria_orden"}, 2]}, ctx) is True


# --- qué hechos deja una respuesta ---------------------------------------------------


def test_una_respuesta_simple_deja_los_hechos_de_su_opcion():
    pregunta = Pregunta(
        code="op.exp.inventario",
        tipo="SINGLE",
        opciones=(Opcion("excel", emits={"inventario": "excel"}),),
    )
    assert hechos_de_respuesta(pregunta, "excel") == {"inventario": "excel"}
    assert hechos_de_respuesta(pregunta, None) == {}


def test_una_respuesta_multiple_junta_los_valores_de_la_misma_clave(cuestionario):
    acceso = cuestionario[1]
    assert hechos_de_respuesta(acceso, ["tarjeta", "llave"]) == {"cpd_acceso": ["tarjeta", "llave"]}


def test_las_listas_emitidas_se_concatenan_sin_repetir():
    pregunta = Pregunta(
        code="op.acc.autenticacion.internos",
        tipo="MULTI",
        opciones=(
            Opcion("password", emits={"auth_internos": ["password"]}),
            Opcion("mfa", emits={"auth_internos": ["mfa"]}),
        ),
    )
    assert hechos_de_respuesta(pregunta, ["password", "mfa", "password"]) == {
        "auth_internos": ["password", "mfa"]
    }


def test_las_preguntas_numericas_dejan_un_hecho_por_casilla():
    pregunta = Pregunta(
        code="op.exp.antimalware.cobertura",
        tipo="NUMBER",
        campos=(Campo("equipos_total"), Campo("equipos_protegidos")),
    )
    assert hechos_de_respuesta(pregunta, {"equipos_total": 60, "equipos_protegidos": 54}) == {
        "equipos_total": 60,
        "equipos_protegidos": 54,
    }


def test_las_tablas_dejan_un_hecho_por_columna():
    pregunta = Pregunta(
        code="op.ext.proveedores",
        tipo="LIST",
        campos=(Campo("proveedor"), Campo("critico")),
    )
    filas = [{"proveedor": "Acme", "critico": "sí"}, {"proveedor": "Beta", "critico": ""}]
    assert hechos_de_respuesta(pregunta, filas) == {
        "proveedor": ["Acme", "Beta"],
        "critico": ["sí"],
    }


def test_una_fecha_se_sustituye_en_el_hecho_que_declara_la_pregunta():
    pregunta = Pregunta(
        code="mp.if.energia.prueba",
        tipo="DATE",
        emits={"energia_ultima_prueba": "$value"},
    )
    assert hechos_de_respuesta(pregunta, "2026-03-11") == {"energia_ultima_prueba": "2026-03-11"}


def test_una_herramienta_deja_el_producto_declarado_bajo_su_funcion():
    """Es el enganche con `SecurityComponent` y con las pistas por producto (§10bis.2b)."""
    pregunta = Pregunta(
        code="op.exp.antimalware",
        tipo="TOOL",
        funcion="EPP_EDR",
        opciones=(Opcion("contratado", emits={"antimalware": "contratado"}),),
    )
    valor = {
        "opcion": "contratado",
        "productos": [{"fabricante": "Microsoft", "producto": "Defender for Endpoint"}],
    }
    assert hechos_de_respuesta(pregunta, valor) == {
        "antimalware": "contratado",
        "herramienta_epp_edr": ["Defender for Endpoint"],
    }


# --- qué evidencias se piden ---------------------------------------------------------


PLANTILLAS = (
    Plantilla(
        code="EV-mp.if.1-01",
        measure="mp.if.1",
        option_group="mp.if.1.acceso",
        preferencia=2,
        titulo="Captura del control de accesos",
        applies_if={"in": [{"var": "hechos.cpd_acceso"}, ["tarjeta", "biometria"]]},
    ),
    Plantilla(
        code="EV-mp.if.1-02",
        measure="mp.if.1",
        option_group="mp.if.1.acceso",
        preferencia=1,
        titulo="Registro de entradas y salidas",
        applies_if={"in": [{"var": "hechos.cpd_acceso"}, ["tarjeta", "biometria"]]},
    ),
    Plantilla(
        code="EV-mp.if.1-03",
        measure="mp.if.1",
        titulo="Registro en papel de la llave",
        applies_if={"==": [{"var": "hechos.cpd_acceso"}, "llave"]},
    ),
    Plantilla(
        code="EV-op.ext.1-01",
        measure="op.ext.1",
        titulo="Contrato con el proveedor",
        applies_if={"==": [{"var": "hechos.instalacion_externa"}, True]},
    ),
    Plantilla(
        code="EV-mp.if.1-r1",
        measure="mp.if.1",
        refuerzo="mp.if.1.r1",
        titulo="Grabaciones del circuito cerrado",
    ),
)

APLICABLES = ("mp.if.1", "op.ext.1", "mp.if.7")


def test_solo_se_piden_evidencias_de_lo_que_esta_en_la_declaracion_de_aplicabilidad():
    ctx = contexto(cpd_acceso="tarjeta", instalacion_externa=True)
    resultado = derivar_requisitos(PLANTILLAS, ctx, medidas_aplicables=["mp.if.1"])
    assert "EV-op.ext.1-01" not in resultado.codigos


def test_un_refuerzo_no_activo_no_pide_su_evidencia():
    ctx = contexto(cpd_acceso="tarjeta")
    sin_refuerzo = derivar_requisitos(PLANTILLAS, ctx, APLICABLES)
    con_refuerzo = derivar_requisitos(PLANTILLAS, ctx, APLICABLES, refuerzos_activos=["mp.if.1.r1"])
    assert "EV-mp.if.1-r1" not in sin_refuerzo.codigos
    assert "EV-mp.if.1-r1" in con_refuerzo.codigos


def test_las_alternativas_del_mismo_grupo_salen_juntas_y_por_solidez():
    """Basta una: el grupo llega ordenado, la más sólida para el auditor primero (§4 M5)."""
    ctx = contexto(cpd_acceso="tarjeta")
    resultado = derivar_requisitos(PLANTILLAS, ctx, APLICABLES)
    assert resultado.grupos["mp.if.1.acceso"] == ("EV-mp.if.1-02", "EV-mp.if.1-01")


def test_la_carpeta_no_pide_nada_de_lo_que_el_sistema_no_tiene():
    ctx = contexto(cpd_acceso="llave")
    resultado = derivar_requisitos(PLANTILLAS, ctx, APLICABLES)
    assert resultado.codigos == {"EV-mp.if.1-03"}


def test_se_avisa_de_las_medidas_aplicables_que_se_quedan_sin_evidencia():
    ctx = contexto(cpd_acceso="llave")
    resultado = derivar_requisitos(PLANTILLAS, ctx, APLICABLES)
    assert resultado.medidas_sin_evidencia == ("mp.if.7", "op.ext.1")


def test_cada_requisito_guarda_la_respuesta_que_lo_origino():
    """Lo que el índice del paquete enseña al auditor: por qué está este hueco (§10bis.4)."""
    ctx = contexto(cpd_acceso="tarjeta")
    resultado = derivar_requisitos(PLANTILLAS, ctx, APLICABLES)
    requisito = next(r for r in resultado.requisitos if r.code == "EV-mp.if.1-02")
    assert requisito.origen["hechos"] == {"cpd_acceso": "tarjeta"}
    assert requisito.origen["preguntas"] == ["mp.if.areas"]
    assert "mp.if.1" in requisito.motivo


def test_la_carpeta_esta_vacia_mientras_no_se_sepa_nada_del_sistema():
    resultado = derivar_requisitos(PLANTILLAS, contexto(), APLICABLES)
    assert resultado.codigos == frozenset()


# --- recalcular sin romper nada ------------------------------------------------------


def test_recalcular_da_de_alta_lo_nuevo_y_aparta_lo_que_ya_no_toca_sin_borrarlo():
    actuales = {"EV-mp.if.1-02": "VALIDADA", "EV-mp.if.1-03": "APORTADA"}
    cambios = reconciliar(actuales, ["EV-mp.if.1-02", "EV-op.ext.1-01"])
    assert cambios.altas == ("EV-op.ext.1-01",)
    assert cambios.fuera_de_alcance == ("EV-mp.if.1-03",)
    assert cambios.sin_cambio == ("EV-mp.if.1-02",)


def test_volver_a_la_respuesta_de_antes_recupera_el_requisito_con_lo_que_ya_tenia():
    actuales = {"EV-mp.if.1-03": "FUERA_DE_ALCANCE"}
    cambios = reconciliar(actuales, ["EV-mp.if.1-03"])
    assert cambios.reactivados == ("EV-mp.if.1-03",)
    assert cambios.altas == ()


def test_sin_cambios_no_hay_nada_que_hacer():
    actuales = {"EV-mp.if.1-02": "VALIDADA"}
    assert reconciliar(actuales, ["EV-mp.if.1-02"]).hay_cambios is False


# --- bordes del contexto y de las respuestas ----------------------------------------


def test_el_contexto_sabe_el_nivel_de_cada_dimension_y_rechaza_lo_que_no_es_una():
    ctx = contexto(instalacion_cpd=True)
    assert ctx.nivel("D") == "ALTO"
    assert ctx.nivel("Z") == "NA"

    nivel_orden = ctx.datos["nivel_orden"]
    assert list(nivel_orden) == ["C", "I", "T", "A", "D"]
    assert len(nivel_orden) == 5
    with pytest.raises(KeyError):
        nivel_orden["ZZ"]


def test_una_pregunta_de_si_o_no_admite_el_booleano_ademas_del_codigo():
    pregunta = Pregunta(
        code="op.exp.vuelta_atras",
        tipo="BOOL",
        opciones=(Opcion("si", emits={"rollback": True}), Opcion("no", emits={"rollback": False})),
    )
    assert hechos_de_respuesta(pregunta, True) == {"rollback": True}
    assert hechos_de_respuesta(pregunta, "no") == {"rollback": False}
    assert hechos_de_respuesta(pregunta, {"opcion": "si"}) == {"rollback": True}


def test_una_pregunta_numerica_sin_casillas_usa_el_hecho_que_declara():
    pregunta = Pregunta(code="org.personas", tipo="NUMBER", emits={"personas": "$value"})
    assert hechos_de_respuesta(pregunta, 48) == {"personas": 48}


def test_una_herramienta_declarada_a_pelo_tambien_cuenta():
    pregunta = Pregunta(code="mp.com.firewall", tipo="TOOL", funcion="FIREWALL")
    assert hechos_de_respuesta(pregunta, ["FortiGate 60F"]) == {
        "herramienta_firewall": ["FortiGate 60F"]
    }
    assert hechos_de_respuesta(pregunta, "FortiGate 60F") == {
        "herramienta_firewall": ["FortiGate 60F"]
    }
    assert hechos_de_respuesta(pregunta, {"productos": []}) == {}


def test_la_carpeta_se_puede_leer_por_medida():
    ctx = contexto(cpd_acceso="tarjeta")
    resultado = derivar_requisitos(PLANTILLAS, ctx, APLICABLES)
    por_medida = resultado.por_medida()
    assert set(por_medida) == {"mp.if.1"}
    assert [r.code for r in por_medida["mp.if.1"]] == ["EV-mp.if.1-02", "EV-mp.if.1-01"]
