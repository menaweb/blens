"""Endpoints del catálogo: consulta y derivación de aplicabilidad."""

import json

import pytest
from django.test import Client


@pytest.fixture
def cliente():
    return Client()


def post(cliente, url, payload):
    return cliente.post(url, data=json.dumps(payload), content_type="application/json")


def test_lista_las_versiones(cliente, catalogo_importado):
    datos = cliente.get("/api/catalog/versions").json()
    assert datos[0]["code"] == catalogo_importado.code
    assert datos[0]["is_current"] is True


def test_filtra_medidas_por_familia(cliente, catalogo_importado):
    datos = cliente.get("/api/catalog/measures?familia=op.exp").json()
    assert len(datos) == 10
    assert {m["marco"] for m in datos} == {"op"}


def test_busca_medidas_por_nombre(cliente, catalogo_importado):
    datos = cliente.get("/api/catalog/measures?q=copias").json()
    assert any(m["code"] == "mp.info.6" for m in datos)


def test_detalle_de_una_medida_con_refuerzos_e_items(cliente, catalogo_importado):
    datos = cliente.get("/api/catalog/measures/op.exp.6").json()
    assert datos["nombre"]
    assert datos["familia"] == "op.exp"
    assert len(datos["items"]) > 0
    assert all("code" in r and "opcional" in r for r in datos["refuerzos"])


def test_medida_inexistente_da_404(cliente, catalogo_importado):
    assert cliente.get("/api/catalog/measures/no.existe").status_code == 404


def test_aplicabilidad_deriva_la_categoria_si_no_se_da(cliente, catalogo_importado):
    datos = post(cliente, "/api/catalog/applicability", {"C": "MEDIO", "D": "BAJO"}).json()
    assert datos["categoria"] == "MEDIA"
    assert datos["total_aplicables"] > 0


def test_aplicabilidad_en_alta_devuelve_las_73(cliente, catalogo_importado):
    payload = {"categoria": "ALTA", "C": "ALTO", "I": "ALTO", "T": "ALTO", "A": "ALTO", "D": "ALTO"}
    datos = post(cliente, "/api/catalog/applicability", payload).json()
    assert datos["total_aplicables"] == 73
    assert datos["no_aplicables"] == []


def test_la_aplicabilidad_explica_cada_medida(cliente, catalogo_importado):
    datos = post(cliente, "/api/catalog/applicability", {"C": "BAJO"}).json()
    assert all(m["motivo"] for m in datos["aplicables"])
    assert all(motivo for _, motivo in datos["no_aplicables"])


def test_la_aplicabilidad_saca_las_selecciones_pendientes(cliente, catalogo_importado):
    payload = {"C": "MEDIO", "I": "MEDIO", "T": "MEDIO", "A": "MEDIO", "D": "MEDIO"}
    datos = post(cliente, "/api/catalog/applicability", payload).json()
    params = {s["param_id"] for s in datos["selecciones_pendientes"]}
    assert "op.acc.5.prm.rfz.medio" in params
    assert all(len(s["opciones"]) > 1 for s in datos["selecciones_pendientes"])


def test_el_catalogo_es_de_solo_lectura(cliente, catalogo_importado):
    """No hay forma de escribir en el catálogo desde la API (roles §1, punto 4)."""
    assert cliente.post("/api/catalog/measures").status_code == 405
    assert cliente.delete("/api/catalog/measures/op.exp.6").status_code == 405


def test_vocabulario(cliente):
    datos = cliente.get("/api/catalog/dimensiones").json()
    assert datos["categorias"] == ["BASICA", "MEDIA", "ALTA"]
    assert datos["dimensiones"] == ["C", "I", "T", "A", "D"]
