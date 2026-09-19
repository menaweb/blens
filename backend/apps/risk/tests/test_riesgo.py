"""Análisis de riesgos sobre datos reales (M7).

La aritmética está probada en `engines/risk_engine`; aquí se prueba el puente: que el
inventario del cliente llega bien al motor, que la madurez del checklist es la que manda
y que un ciclo se le devuelve al cliente en castellano.
"""

import json

import pytest

from apps.compliance.models import MeasureAssessment
from apps.risk.models import Asset, AssetDependency, RiskResult, ThreatInstance
from apps.risk.services import amenazas_por_defecto, recalcular
from apps.risk.tasks import recalcular_riesgo
from apps.tenancy.models import Role
from apps.tenancy.testing import como


def post(cliente, url, payload=None):
    return cliente.post(url, data=json.dumps(payload or {}), content_type="application/json")


@pytest.fixture
def con_dos(sistema, sede_y_servidor):
    """El servidor con sus amenazas propuestas por el catálogo."""
    _, servidor = sede_y_servidor
    amenazas_por_defecto(servidor)
    return servidor


# --- Propagación y cálculo -----------------------------------------------------------


def test_el_valor_del_servicio_llega_al_servidor(con_dos, sistema):
    recalcular(sistema)
    resultado = RiskResult.objects.filter(threat_instance__asset=con_dos).first()
    assert resultado.accumulated_value == 9


def test_sin_madurez_declarada_el_residual_es_el_intrinseco(con_dos, sistema):
    recalcular(sistema)
    for resultado in RiskResult.objects.filter(threat_instance__asset=con_dos):
        assert resultado.residual_risk == resultado.intrinsic_risk


def test_subir_la_madurez_baja_el_riesgo(con_dos, sistema):
    """El acoplamiento riesgo↔cumplimiento, sobre datos de verdad.

    Se comparan solo las amenazas con riesgo real: las que caen sobre una dimensión que
    ese activo no hereda valen 0 antes y después, y bajar de 0 no es posible.
    """
    recalcular(sistema)
    antes = {
        r.threat_instance_id: r.residual_risk
        for r in RiskResult.objects.filter(intrinsic_risk__gt=0)
    }

    MeasureAssessment.objects.filter(system=sistema).update(maturity_level=5)
    recalcular(sistema)
    despues = {r.threat_instance_id: r.residual_risk for r in RiskResult.objects.all()}

    assert antes  # había algo que bajar
    assert all(despues[clave] <= antes[clave] for clave in antes)
    assert any(despues[clave] < antes[clave] for clave in antes)
    # Y ninguna baja a cero: la amenaza se contiene, no desaparece.
    assert all(despues[clave] > 0 for clave in antes)


def test_una_medida_marcada_como_no_aplicable_no_frena_nada(con_dos, sistema):
    MeasureAssessment.objects.filter(system=sistema).update(maturity_level=5)
    recalcular(sistema)
    con_salvaguardas = {r.threat_instance_id: r.residual_risk for r in RiskResult.objects.all()}

    MeasureAssessment.objects.filter(system=sistema).update(applies=False)
    recalcular(sistema)
    sin_ellas = {r.threat_instance_id: r.residual_risk for r in RiskResult.objects.all()}

    assert all(sin_ellas[clave] >= con_salvaguardas[clave] for clave in sin_ellas)


def test_la_traza_dice_que_madurez_se_uso(con_dos, sistema):
    MeasureAssessment.objects.filter(system=sistema).update(maturity_level=3)
    recalcular(sistema)
    resultado = RiskResult.objects.exclude(salvaguardas=[]).first()
    assert resultado.salvaguardas[0]["nivel"] == 3
    assert resultado.salvaguardas[0]["measure"]
    assert resultado.salvaguardas[0]["aspect"] in ("FREQ", "IMPACT")


def test_recalcular_reescribe_y_no_acumula(con_dos, sistema):
    recalcular(sistema)
    cuantos = RiskResult.objects.count()
    assert recalcular(sistema) == cuantos
    assert RiskResult.objects.count() == cuantos


def test_un_sistema_sin_amenazas_no_falla(sistema):
    assert recalcular(sistema) == 0


def test_borrar_una_amenaza_borra_su_resultado(con_dos, sistema):
    recalcular(sistema)
    instancia = ThreatInstance.objects.filter(asset=con_dos).first()
    instancia.delete()
    recalcular(sistema)
    assert not RiskResult.objects.filter(threat_instance_id=instancia.pk).exists()


# --- Amenazas propuestas ---------------------------------------------------------------


def test_el_catalogo_propone_amenazas_segun_el_tipo(sede_y_servidor, tipo, sistema):
    _, servidor = sede_y_servidor
    creadas = amenazas_por_defecto(servidor)
    assert creadas > 0
    codigos = set(
        ThreatInstance.objects.filter(asset=servidor).values_list("threat__code", flat=True)
    )
    assert "N.1" in codigos  # el fuego aplica al hardware
    assert "A.24" in codigos  # y la denegación de servicio también


def test_no_pisa_lo_que_el_cliente_ya_ajusto(sede_y_servidor, sistema):
    _, servidor = sede_y_servidor
    amenazas_por_defecto(servidor)
    instancia = ThreatInstance.objects.filter(asset=servidor).first()
    instancia.frequency = 42
    instancia.save()

    assert amenazas_por_defecto(servidor) == 0
    instancia.refresh_from_db()
    assert instancia.frequency == 42


def test_las_amenazas_de_datos_no_son_las_del_hardware(sistema, tipo):
    datos = Asset.objects.create(
        tenant=sistema.tenant, system=sistema, asset_type=tipo("D.personal"), nombre="Padrón"
    )
    amenazas_por_defecto(datos)
    codigos = set(ThreatInstance.objects.filter(asset=datos).values_list("threat__code", flat=True))
    assert "N.1" not in codigos  # los datos no se queman, se quema el soporte
    assert codigos


# --- Ciclos ------------------------------------------------------------------------------


def test_un_ciclo_se_devuelve_explicado_y_no_rompe_la_tarea(sede_y_servidor, sistema):
    sede, servidor = sede_y_servidor
    amenazas_por_defecto(servidor)
    AssetDependency.objects.create(parent=servidor, child=sede, degree=1)

    respuesta = recalcular_riesgo(sistema.pk)
    assert respuesta["estado"] == "CICLO"
    assert len(respuesta["ciclo"]) >= 3
    assert "círculo" in respuesta["mensaje"]


def test_un_activo_no_puede_depender_de_si_mismo(sede_y_servidor, tecnico, sistema):
    sede, _ = sede_y_servidor
    respuesta = post(
        como(tecnico),
        f"/api/systems/{sistema.pk}/dependencies",
        {"parent": sede.pk, "child": sede.pk},
    )
    assert respuesta.status_code == 400


# --- API ---------------------------------------------------------------------------------


def test_alta_de_activo_con_amenazas_propuestas(sistema, tecnico):
    respuesta = post(
        como(tecnico),
        f"/api/systems/{sistema.pk}/assets",
        {"nombre": "Cabina de discos", "tipo": "HW", "valores": {"D": 7}},
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["valores"]["D"] == 7
    assert ThreatInstance.objects.filter(asset__nombre="Cabina de discos").exists()


def test_no_se_repite_el_nombre_de_un_activo(sistema, tecnico):
    cliente = como(tecnico)
    cuerpo = {"nombre": "Cabina", "tipo": "HW", "proponer_amenazas": False}
    assert post(cliente, f"/api/systems/{sistema.pk}/assets", cuerpo).status_code == 200
    assert post(cliente, f"/api/systems/{sistema.pk}/assets", cuerpo).status_code == 409


def test_un_activo_no_se_valora_por_encima_de_diez(sistema, tecnico):
    respuesta = post(
        como(tecnico),
        f"/api/systems/{sistema.pk}/assets",
        {"nombre": "X", "tipo": "HW", "valores": {"D": 11}},
    )
    assert respuesta.status_code == 400


def test_la_lista_de_riesgos_sale_del_mas_grave_al_menos(con_dos, sistema, tecnico):
    recalcular(sistema)
    respuesta = como(tecnico).get(f"/api/systems/{sistema.pk}/risks")
    assert respuesta.status_code == 200
    residuales = [r["riesgo_residual"] for r in respuesta.json()]
    assert residuales == sorted(residuales, reverse=True)


def test_recalcular_desde_la_api(con_dos, sistema, tecnico):
    respuesta = post(como(tecnico), f"/api/systems/{sistema.pk}/risks/recompute")
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "ENCOLADO"
    assert RiskResult.objects.exists()


def test_el_simulador_dice_que_subir(con_dos, sistema, tecnico):
    MeasureAssessment.objects.filter(system=sistema).update(maturity_level=1)
    recalcular(sistema)
    peor = RiskResult.objects.order_by("-residual_risk").first()
    objetivo = float(peor.residual_risk) / 2

    respuesta = post(
        como(tecnico),
        f"/api/risks/{peor.threat_instance_id}/simulate",
        {"objetivo": objetivo},
    )
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["riesgo_final"] <= datos["riesgo_inicial"]
    assert all(s["nivel_propuesto"] > s["nivel_actual"] for s in datos["subidas"])


def test_no_se_simula_sobre_lo_que_no_se_ha_calculado(con_dos, sistema, tecnico):
    instancia = ThreatInstance.objects.filter(asset=con_dos).first()
    respuesta = post(como(tecnico), f"/api/risks/{instancia.pk}/simulate", {"objetivo": 1})
    assert respuesta.status_code == 409


# --- Tratamiento ----------------------------------------------------------------------------


def test_el_tratamiento_arranca_sin_decidir(con_dos, sistema, tecnico):
    recalcular(sistema)
    respuesta = como(tecnico).get(f"/api/systems/{sistema.pk}/risks")
    assert all(r["decision"] == "" for r in respuesta.json())


def test_mitigar_lo_decide_el_tecnico(con_dos, sistema, tecnico):
    instancia = ThreatInstance.objects.filter(asset=con_dos).first()
    respuesta = como(tecnico).put(
        f"/api/risks/{instancia.pk}/treatment",
        data=json.dumps({"decision": "MITIGAR", "target_risk": 2.0}),
        content_type="application/json",
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["decision"] == "MITIGAR"


def test_aceptar_un_riesgo_no_lo_decide_un_tecnico(con_dos, sistema, tecnico):
    """Asumir un riesgo es decisión de dirección o del RSEG, y queda registrado."""
    instancia = ThreatInstance.objects.filter(asset=con_dos).first()
    respuesta = como(tecnico).put(
        f"/api/risks/{instancia.pk}/treatment",
        data=json.dumps({"decision": "ACEPTAR"}),
        content_type="application/json",
    )
    assert respuesta.status_code == 403


def test_el_rseg_acepta_y_queda_su_firma(con_dos, sistema, rseg):
    instancia = ThreatInstance.objects.filter(asset=con_dos).first()
    respuesta = como(rseg).put(
        f"/api/risks/{instancia.pk}/treatment",
        data=json.dumps({"decision": "ACEPTAR", "notes": "Riesgo asumido por dirección."}),
        content_type="application/json",
    )
    assert respuesta.status_code == 200
    instancia.refresh_from_db()
    assert instancia.tratamiento.aceptado_por == rseg
    assert instancia.tratamiento.aceptado_en is not None


def test_una_decision_inventada_se_rechaza(con_dos, sistema, rseg):
    instancia = ThreatInstance.objects.filter(asset=con_dos).first()
    respuesta = como(rseg).put(
        f"/api/risks/{instancia.pk}/treatment",
        data=json.dumps({"decision": "IGNORAR"}),
        content_type="application/json",
    )
    assert respuesta.status_code == 400


def test_el_colaborador_no_entra_al_riesgo(con_dos, sistema, miembro):
    colaborador = miembro(Role.COLABORADOR, bloques=["B3"])
    assert como(colaborador).get(f"/api/systems/{sistema.pk}/risks").status_code == 403
