"""Humo de Celery: la app existe y la tarea de prueba está registrada."""

from config.celery import app, ping


def test_la_tarea_de_prueba_responde():
    assert ping.run() == "pong"


def test_la_app_celery_lee_la_configuracion_de_django():
    assert app.conf.task_serializer == "json"
    assert app.conf.broker_transport_options["region"] == "eu-west-1"
