"""Proyecto Django de BLENS.

El worker de Celery arranca con `celery -A config`, que importa este paquete y **no**
pasa por `manage.py`, así que aquí es donde se asegura que la raíz del repositorio esté
en el path: los motores de `engines/` son paquetes del repo, no dependencias instaladas.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
for ruta in (str(BACKEND_DIR), str(REPO_DIR)):
    if ruta not in sys.path:
        sys.path.insert(0, ruta)

from .celery import app as celery_app  # noqa: E402

__all__ = ("celery_app",)
