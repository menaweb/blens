"""Perfilado (M11): responder cambia lo que se pregunta y lo que se pide.

Lo que se prueba aquí no es el motor —eso está en `engines/evidence_engine`— sino que la
base de datos y la API hacen lo que el motor decide, y que responder tiene consecuencias
visibles: aparecen preguntas nuevas y aparecen huecos nuevos en la carpeta.
"""

import json

import pytest

from apps.evidence.models import EvidenceRequirement
from apps.profiling.models import ProfileAnswer, ProfileAnswerHistory, ProfileFact
from apps.profiling.services import contexto_de, delegar, preguntas_pendientes, responder
from apps.tenancy.models import Role
from apps.tenancy.testing import como


def put(cliente, url, payload):
    return cliente.put(url, data=json.dumps(payload), content_type="application/json")


@pytest.fixture
def rseg(miembro):
    return miembro(Role.RSEG)


# --- Respuestas y hechos ---------------------------------------------------------


def test_responder_deja_los_hechos_que_declara_la_opcion(sistema, pregunta, rseg):
    responder(sistema, pregunta("mp.if.areas"), ["cpd"], usuario=rseg)

    hechos = dict(ProfileFact.objects.filter(system=sistema).values_list("key", "value"))
    assert hechos == {"instalacion_cpd": True}
    assert contexto_de(sistema).origen["instalacion_cpd"] == "mp.if.areas"


def test_una_pregunta_de_seguimiento_solo_aparece_cuando_toca(sistema, pregunta, rseg):
    antes = {p.code for p in preguntas_pendientes(sistema)}
    assert "mp.if.acceso" not in antes

    responder(sistema, pregunta("mp.if.areas"), ["cpd"], usuario=rseg)

    despues = {p.code for p in preguntas_pendientes(sistema)}
    assert "mp.if.acceso" in despues
    assert "mp.if.areas" not in despues, "una pregunta respondida no sigue pendiente"


def test_responder_llena_la_carpeta_de_evidencias(sistema, pregunta, rseg):
    cambios = responder(sistema, pregunta("mp.if.areas"), ["cpd"], usuario=rseg)

    assert cambios["requisitos_nuevos"], "responder no ha pedido ninguna evidencia"
    assert EvidenceRequirement.objects.filter(system=sistema).exists()


def test_corregir_una_respuesta_guarda_la_anterior(sistema, pregunta, rseg):
    mp_if_areas = pregunta("mp.if.areas")
    responder(sistema, mp_if_areas, ["cpd"], usuario=rseg)
    responder(sistema, mp_if_areas, ["proveedor"], usuario=rseg)

    respuesta = ProfileAnswer.objects.get(system=sistema, question=mp_if_areas)
    assert respuesta.value == ["proveedor"]
    assert [h.value for h in ProfileAnswerHistory.objects.filter(answer=respuesta)] == [["cpd"]]


def test_un_hecho_que_deja_de_emitirse_desaparece(sistema, pregunta, rseg):
    """Si el CPD pasa a ser de un proveedor, no puede quedar un `instalacion_cpd` viejo."""
    mp_if_areas = pregunta("mp.if.areas")
    responder(sistema, mp_if_areas, ["cpd"], usuario=rseg)
    responder(sistema, mp_if_areas, ["proveedor"], usuario=rseg)

    hechos = dict(ProfileFact.objects.filter(system=sistema).values_list("key", "value"))
    assert hechos == {"instalacion_externa": True}


def test_cambiar_la_respuesta_aparta_lo_que_ya_no_toca_sin_borrarlo(sistema, pregunta, rseg):
    mp_if_areas = pregunta("mp.if.areas")
    responder(sistema, mp_if_areas, ["cpd"], usuario=rseg)
    antes = set(
        EvidenceRequirement.objects.filter(system=sistema).values_list("template__code", flat=True)
    )

    cambios = responder(sistema, mp_if_areas, ["proveedor"], usuario=rseg)

    assert cambios["requisitos_fuera_de_alcance"]
    # No se borra ninguno: los de antes siguen ahí, apartados.
    despues = set(
        EvidenceRequirement.objects.filter(system=sistema).values_list("template__code", flat=True)
    )
    assert antes <= despues
    apartados = EvidenceRequirement.objects.filter(
        system=sistema, estado="FUERA_DE_ALCANCE"
    ).count()
    assert apartados == len(cambios["requisitos_fuera_de_alcance"])


# --- Delegar en vez de «no lo sé» --------------------------------------------------


def test_delegar_exige_decir_a_quien(sistema, pregunta, rseg):
    with pytest.raises(ValueError):
        delegar(sistema, pregunta("mp.if.areas"), usuario=rseg)


def test_responder_cierra_la_delegacion_pendiente(sistema, pregunta, rseg, miembro):
    tecnico = miembro(Role.TECNICO)
    delegacion = delegar(sistema, pregunta("mp.if.areas"), usuario=rseg, asignado=tecnico)

    responder(sistema, pregunta("mp.if.areas"), ["cpd"], usuario=tecnico)

    delegacion.refresh_from_db()
    assert delegacion.estado == "RESUELTA"


# --- API ---------------------------------------------------------------------------


def test_el_cuestionario_llega_con_la_ayuda_para_poder_contestarlo(sistema, rseg):
    respuesta = como(rseg).get(f"/api/systems/{sistema.pk}/profiling")
    assert respuesta.status_code == 200

    datos = respuesta.json()
    assert datos["pendientes"] > 0
    assert datos["bloques"], "el cuestionario no dice por dónde se empieza"
    primera = datos["preguntas"][0]
    assert primera["por_que"], "una pregunta sin «por qué» parece burocracia"
    assert "no lo sé" not in {o["label"].lower() for o in primera["opciones"]}


def test_responder_por_la_api_devuelve_lo_que_ha_cambiado(sistema, rseg):
    respuesta = put(
        como(rseg), f"/api/systems/{sistema.pk}/profiling/mp.if.areas", {"valor": ["cpd"]}
    )
    assert respuesta.status_code == 200

    datos = respuesta.json()
    assert datos["hechos"] == {"instalacion_cpd": True}
    assert datos["requisitos_nuevos"]
    assert "mp.if.acceso" in {p["code"] for p in datos["cuestionario"]["preguntas"]}


def test_el_colaborador_solo_responde_los_bloques_que_le_han_dado(sistema, miembro):
    """`can()` acota por bloque; el perfilado se reparte así (docs/roles_y_permisos.md)."""
    colaborador = miembro(Role.COLABORADOR, bloques=["B04"])  # instalaciones
    cliente = como(colaborador)

    suyo = put(cliente, f"/api/systems/{sistema.pk}/profiling/mp.if.areas", {"valor": ["cpd"]})
    assert suyo.status_code == 200

    ajeno = put(  # op.exp.inventario vive en B07, que no le han dado
        cliente, f"/api/systems/{sistema.pk}/profiling/op.exp.inventario", {"valor": "excel"}
    )
    assert ajeno.status_code == 403


def test_sin_credenciales_no_se_ve_el_perfilado(sistema, anonimo):
    assert anonimo.get(f"/api/systems/{sistema.pk}/profiling").status_code == 401
