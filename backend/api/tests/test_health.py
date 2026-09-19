"""La API responde y el OpenAPI se genera (criterios de cierre de F0)."""

import pytest
from django.test import Client


@pytest.mark.django_db
def test_health_responde():
    respuesta = Client().get("/api/health")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "ok"
    assert cuerpo["database"] == "ok"


def test_el_openapi_se_genera_y_documenta_health():
    from api.urls import api

    esquema = api.get_openapi_schema()
    assert esquema["info"]["title"] == "BLENS API"
    assert "/api/health" in esquema["paths"]
