"""Montaje de la API. Django Ninja genera el OpenAPI del que salen los tipos del frontend."""

from ninja import NinjaAPI

from api.routers.catalog import router as catalog_router
from api.routers.categorization import router as categorization_router
from api.routers.dda import router as dda_router
from api.routers.health import router as health_router

api = NinjaAPI(
    title="BLENS API",
    version="0.1.0",
    description="API de la plataforma de cumplimiento del ENS.",
    docs_url="/docs",
)

api.add_router("/health", health_router, tags=["infraestructura"])
api.add_router("/catalog", catalog_router, tags=["catálogo"])
api.add_router("/categorization", categorization_router, tags=["categorización"])
api.add_router("", dda_router, tags=["declaración de aplicabilidad"])
