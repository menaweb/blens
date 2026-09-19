"""Montaje de la API. Django Ninja genera el OpenAPI del que salen los tipos del frontend."""

from ninja import NinjaAPI

from api.routers.health import router as health_router

api = NinjaAPI(
    title="BLENS API",
    version="0.1.0",
    description="API de la plataforma de cumplimiento del ENS.",
    docs_url="/docs",
)

api.add_router("/health", health_router, tags=["infraestructura"])
