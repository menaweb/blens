"""Aplicación Celery. Broker: Redis en local, SQS en AWS (§5)."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("blens")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(name="config.ping")
def ping() -> str:
    """Tarea de humo: comprueba que el worker responde."""
    return "pong"
