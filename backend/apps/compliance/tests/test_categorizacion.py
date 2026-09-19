"""Categorización del Anexo I (M1): la puerta del producto, y funciona sin cuenta."""

import pytest
from django.test import Client

from apps.compliance.models import InformeCategorizacion, categoria_de


@pytest.fixture
def cliente():
    return Client()


def post(cliente, url, payload):
    import json

    return cliente.post(url, data=json.dumps(payload), content_type="application/json")


# --- La regla del Anexo I ------------------------------------------------------


def test_la_categoria_es_la_mas_alta_de_las_dimensiones():
    assert categoria_de({"C": "BAJO", "I": "MEDIO", "D": "BAJO"}) == "MEDIA"
    assert categoria_de({"C": "ALTO", "I": "NA"}) == "ALTA"
    assert categoria_de({"C": "BAJO"}) == "BASICA"


def test_si_todo_es_no_aplica_no_hay_categoria():
    """Regla del handoff: no se inventa una Básica, se avisa de que el alcance está mal."""
    assert categoria_de({d: "NA" for d in "CITAD"}) == ""


# --- El asistente sin cuenta ---------------------------------------------------


def test_categorizar_sin_estar_autenticado(cliente, catalogo):
    respuesta = post(cliente, "/api/categorization/preview", {"C": "MEDIO", "D": "BAJO"})
    assert respuesta.status_code == 200

    datos = respuesta.json()
    assert datos["categoria"] == "MEDIA"
    assert datos["madurez_minima"] == 3
    assert datos["requiere_certificacion"] is True
    assert datos["resumen"]["medidas"] > 0


def test_basica_se_resuelve_con_autoevaluacion(cliente, catalogo):
    datos = post(cliente, "/api/categorization/preview", {"C": "BAJO"}).json()
    assert datos["categoria"] == "BASICA"
    assert datos["requiere_certificacion"] is False
    assert datos["madurez_minima"] == 2


def test_el_resultado_dice_que_dimension_marca_la_categoria(cliente, catalogo):
    datos = post(
        cliente, "/api/categorization/preview", {"C": "BAJO", "A": "ALTO", "T": "ALTO"}
    ).json()
    marcan = [d["dim"] for d in datos["dimensiones"] if d["marca_categoria"]]
    assert sorted(marcan) == ["A", "T"]


def test_sin_determinar_no_da_cifras_ni_empuja_a_registrarse(cliente, catalogo):
    datos = post(cliente, "/api/categorization/preview", {}).json()
    assert datos["sin_determinar"] is True
    assert datos["categoria"] == ""
    assert datos["resumen"] == {}
    assert "alcance" in datos["aviso"]


def test_una_dimension_alta_suma_medidas_aunque_la_categoria_no_cambie(cliente, catalogo):
    """Anexo I.4.2: las dimensiones que no marcan la categoría conservan su nivel."""
    sin_trazabilidad = post(cliente, "/api/categorization/preview", {"C": "ALTO"}).json()
    con_trazabilidad = post(
        cliente, "/api/categorization/preview", {"C": "ALTO", "T": "ALTO"}
    ).json()

    assert sin_trazabilidad["categoria"] == con_trazabilidad["categoria"] == "ALTA"
    assert con_trazabilidad["resumen"]["medidas"] > sin_trazabilidad["resumen"]["medidas"]


# --- El PDF --------------------------------------------------------------------


def test_pide_el_pdf_y_se_descarga(cliente, catalogo, sin_pdf):
    """Criterio de cierre: categorizar sin cuenta y descargar el PDF."""
    creado = post(
        cliente,
        "/api/categorization/report",
        {"C": "MEDIO", "I": "MEDIO", "organizacion": "Ayto de Ejemplo", "alcance": "Sede"},
    ).json()
    assert creado["categoria"] == "MEDIA"

    estado = cliente.get(f"/api/categorization/report/{creado['token']}").json()
    assert estado["estado"] == "LISTO"

    descarga = cliente.get(creado["descarga"])
    assert descarga.status_code == 200
    assert descarga["Content-Type"] == "application/pdf"
    assert b"".join(descarga.streaming_content).startswith(b"%PDF")


def test_el_render_va_en_celery_no_en_la_peticion(cliente, catalogo, sin_pdf, monkeypatch):
    """§15: el PDF se encola, nunca se renderiza dentro del ciclo request/response."""
    llamadas = []
    from apps.compliance.tasks import render_categorizacion

    monkeypatch.setattr(render_categorizacion, "delay", lambda *a, **k: llamadas.append(a) or None)
    post(cliente, "/api/categorization/report", {"C": "BAJO"})
    assert len(llamadas) == 1


def test_la_categorizacion_anonima_caduca(cliente, catalogo, sin_pdf):
    post(cliente, "/api/categorization/report", {"C": "BAJO"})
    informe = InformeCategorizacion.objects.get()
    assert informe.tenant is None
    assert informe.expira_en is not None


def test_no_se_descarga_un_informe_caducado(cliente, catalogo, sin_pdf):
    from django.utils import timezone

    creado = post(cliente, "/api/categorization/report", {"C": "BAJO"}).json()
    InformeCategorizacion.objects.update(expira_en=timezone.now() - timezone.timedelta(days=1))
    assert cliente.get(creado["descarga"]).status_code == 404


def test_la_limpieza_borra_las_caducadas(cliente, catalogo, sin_pdf):
    from django.utils import timezone

    from apps.compliance.tasks import limpiar_categorizaciones_caducadas

    post(cliente, "/api/categorization/report", {"C": "BAJO"})
    InformeCategorizacion.objects.update(expira_en=timezone.now() - timezone.timedelta(days=1))

    assert limpiar_categorizaciones_caducadas() == 1
    assert InformeCategorizacion.objects.count() == 0
