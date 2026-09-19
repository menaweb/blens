"""Endpoint de salud. Sirve de humo para el despliegue y de prueba del contrato tipado."""

from django.db import connection
from ninja import Router, Schema

router = Router()


class HealthOut(Schema):
    status: str
    version: str
    database: str


@router.get("", response=HealthOut, summary="Estado del servicio")
def health(request) -> HealthOut:
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        database = "ok"
    except Exception:  # pragma: no cover - depende del entorno
        database = "error"
    return HealthOut(status="ok", version="0.1.0", database=database)
