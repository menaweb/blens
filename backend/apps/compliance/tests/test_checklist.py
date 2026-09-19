"""Checklist de medidas (M4) y el acoplamiento con el riesgo.

Lo que aquí se prueba no es la aritmética —eso está en `engines/scoring_engine`— sino
que la base de datos se traduce bien al motor y que una sola fuente de madurez alimenta
los dos lados.
"""

import json

import pytest
from django.test import Client

from apps.compliance.models import MeasureAssessment
from apps.compliance.services import asegurar_valoraciones, generar_dda, puntuar_sistema
from apps.tenancy.models import Role


def como(usuario):
    cliente = Client()
    cliente.force_login(usuario)
    return cliente


def patch(cliente, url, payload):
    return cliente.patch(url, data=json.dumps(payload), content_type="application/json")


@pytest.fixture
def con_madurez(sistema_media):
    """Una fila de madurez por medida aplicable, sin valorar todavía."""
    asegurar_valoraciones(sistema_media)
    return sistema_media


# --- Creación de las filas --------------------------------------------------------


def test_se_crea_una_fila_por_medida_aplicable(sistema_media):
    creadas = asegurar_valoraciones(sistema_media)
    assert creadas > 0
    assert MeasureAssessment.objects.filter(system=sistema_media).count() == creadas
    # Ninguna nace valorada: sin valorar no es L0, es que nadie la ha mirado.
    assert not MeasureAssessment.objects.filter(
        system=sistema_media, maturity_level__isnull=False
    ).exists()


def test_es_idempotente(con_madurez):
    antes = MeasureAssessment.objects.filter(system=con_madurez).count()
    assert asegurar_valoraciones(con_madurez) == 0
    assert MeasureAssessment.objects.filter(system=con_madurez).count() == antes


def test_manda_la_dda_cuando_existe(sistema_media, rseg):
    """La DdA es la decisión formal: si dice que una medida no aplica, no entra."""
    dda = generar_dda(sistema_media, usuario=rseg)
    fila = dda.medidas.filter(aplica=True).first()
    fila.aplica = False
    fila.justificacion = "No hay servicios en la nube."
    fila.save()

    asegurar_valoraciones(sistema_media)
    assert not MeasureAssessment.objects.filter(
        system=sistema_media, measure__code=fila.measure.code
    ).exists()


def test_sin_categorizar_no_hay_checklist(sistema, rseg):
    assert asegurar_valoraciones(sistema) == 0


# --- Scoring sobre datos reales ----------------------------------------------------


def test_el_sistema_arranca_a_cero(con_madurez):
    resultado = puntuar_sistema(con_madurez)
    assert resultado.objetivo_categoria == 3  # categoría Media → L3
    assert resultado.sistema.cumplimiento == 0
    assert resultado.sistema.con_datos == 0
    # Un cliente nuevo está a cero por definición: el estado vacío informa, no alarma.
    assert resultado.sistema.medidas > 0


def test_subir_una_medida_sube_su_fila_pero_no_el_indice(con_madurez):
    fila = MeasureAssessment.objects.filter(system=con_madurez).first()
    fila.maturity_level = 5
    fila.save()

    resultado = puntuar_sistema(con_madurez)
    assert resultado.medida(fila.measure.code).cumplimiento_pct == 100
    # El índice es el peor componente: una sola medida no lo mueve.
    assert resultado.sistema.cumplimiento == 0


def test_todo_en_objetivo_da_cien(con_madurez):
    MeasureAssessment.objects.filter(system=con_madurez).update(maturity_level=3)
    resultado = puntuar_sistema(con_madurez)
    assert resultado.sistema.cumplimiento == 100
    assert resultado.sistema.en_objetivo == resultado.sistema.medidas
    assert resultado.brechas == ()


def test_excluir_una_medida_desde_el_checklist(con_madurez):
    MeasureAssessment.objects.filter(system=con_madurez).update(maturity_level=3)
    fila = MeasureAssessment.objects.filter(system=con_madurez).first()
    fila.applies = False
    fila.maturity_level = 0
    fila.save()

    resultado = puntuar_sistema(con_madurez)
    assert not resultado.medida(fila.measure.code).aplica
    assert resultado.sistema.cumplimiento == 100


# --- API ---------------------------------------------------------------------------


def test_el_tecnico_ve_y_edita_el_checklist(con_madurez, tecnico):
    cliente = como(tecnico)
    respuesta = cliente.get(f"/api/systems/{con_madurez.pk}/checklist")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["categoria"] == "MEDIA"
    assert datos["objetivo_categoria"] == 3
    assert datos["escala"]["L3"] == "definido"
    assert len(datos["medidas"]) == 73
    assert set(datos["por_marco"]) == {"org", "op", "mp"}

    code = next(m["code"] for m in datos["medidas"] if m["aplica"])
    respuesta = patch(
        cliente, f"/api/systems/{con_madurez.pk}/checklist/{code}", {"maturity_level": 4}
    )
    assert respuesta.status_code == 200
    fila = next(m for m in respuesta.json()["medidas"] if m["code"] == code)
    assert (fila["madurez"], fila["delta"], fila["semaforo"]) == (4, 1, "VERDE")


def test_el_auditor_lee_pero_no_edita(con_madurez, miembro):
    auditor = miembro(Role.AUDITOR)
    cliente = como(auditor)
    assert cliente.get(f"/api/systems/{con_madurez.pk}/checklist").status_code == 200
    code = MeasureAssessment.objects.filter(system=con_madurez).first().measure.code
    respuesta = patch(
        cliente, f"/api/systems/{con_madurez.pk}/checklist/{code}", {"maturity_level": 5}
    )
    assert respuesta.status_code == 403


def test_un_nivel_fuera_de_escala_se_rechaza(con_madurez, tecnico):
    code = MeasureAssessment.objects.filter(system=con_madurez).first().measure.code
    respuesta = patch(
        como(tecnico), f"/api/systems/{con_madurez.pk}/checklist/{code}", {"maturity_level": 9}
    )
    assert respuesta.status_code == 400


def test_se_puede_vaciar_un_nivel_ya_puesto(con_madurez, tecnico):
    code = MeasureAssessment.objects.filter(system=con_madurez).first().measure.code
    cliente = como(tecnico)
    patch(cliente, f"/api/systems/{con_madurez.pk}/checklist/{code}", {"maturity_level": 3})
    respuesta = patch(
        cliente, f"/api/systems/{con_madurez.pk}/checklist/{code}", {"limpiar": ["maturity_level"]}
    )
    fila = next(m for m in respuesta.json()["medidas"] if m["code"] == code)
    assert fila["madurez"] is None
    assert fila["semaforo"] == "GRIS"


def test_no_se_vacia_cualquier_cosa(con_madurez, tecnico):
    code = MeasureAssessment.objects.filter(system=con_madurez).first().measure.code
    respuesta = patch(
        como(tecnico), f"/api/systems/{con_madurez.pk}/checklist/{code}", {"limpiar": ["notas"]}
    )
    assert respuesta.status_code == 400


def test_responsable_fecha_y_notas(con_madurez, tecnico, rseg):
    code = MeasureAssessment.objects.filter(system=con_madurez).first().measure.code
    respuesta = patch(
        como(tecnico),
        f"/api/systems/{con_madurez.pk}/checklist/{code}",
        {"responsable_id": rseg.pk, "fecha_limite": "2027-03-31", "notas": "Pendiente del pliego."},
    )
    fila = next(m for m in respuesta.json()["medidas"] if m["code"] == code)
    assert fila["responsable_id"] == rseg.pk
    assert fila["fecha_limite"] == "2027-03-31"
    assert fila["notas"] == "Pendiente del pliego."


def test_un_sistema_sin_categorizar_no_tiene_checklist(sistema, tecnico):
    respuesta = como(tecnico).get(f"/api/systems/{sistema.pk}/checklist")
    assert respuesta.status_code == 409
