import pytest
from django.core.management import call_command

from apps.catalog.models import CatalogVersion
from apps.compliance.models import System
from apps.compliance.services import guardar_valoracion
from apps.tenancy.models import Role


@pytest.fixture
def catalogo(db):
    from pathlib import Path

    oscal = Path(__file__).resolve().parents[4] / "db/seed/oscal/ENS_Anexo_II_rev_9.json"
    call_command("import_ens_oscal", str(oscal))
    return CatalogVersion.objects.get(is_current=True)


@pytest.fixture
def sistema(db, tenant, catalogo):
    return System.objects.create(tenant=tenant, nombre="Sede electrónica")


@pytest.fixture
def sistema_media(sistema):
    guardar_valoracion(
        sistema, {"C": "MEDIO", "I": "MEDIO", "T": "BAJO", "A": "MEDIO", "D": "BAJO"}
    )
    sistema.refresh_from_db()
    return sistema


@pytest.fixture
def rseg(miembro):
    return miembro(Role.RSEG)


@pytest.fixture
def tecnico(miembro):
    return miembro(Role.TECNICO)


@pytest.fixture(autouse=True)
def celery_sincrono(settings):
    """Las tareas se ejecutan en el momento durante los tests.

    Se configura por los *settings* de Django y no por `app.conf`: la app lee la
    configuración desde `django.conf:settings`, que tiene prioridad sobre lo que se
    asigne a mano en `app.conf` (asignarlo ahí parece funcionar y no hace nada).
    `task_eager_propagates` es igual de importante: sin él, un fallo dentro de la tarea
    se traga y el test miente.
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


@pytest.fixture
def sin_pdf(monkeypatch):
    """Evita depender de pango/cairo: lo que se prueba aquí es el flujo, no WeasyPrint."""
    from apps.compliance import tasks

    monkeypatch.setattr(tasks, "render_pdf", lambda plantilla, contexto: b"%PDF-1.7 falso")
