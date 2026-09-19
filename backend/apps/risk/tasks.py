"""Tareas Celery del análisis de riesgos.

El recálculo recorre el grafo entero y todas las instancias de amenaza: es trabajo
pesado y no va en el ciclo de la petición (§15). La pantalla pide el recálculo, sigue
funcionando y se entera cuando termina.
"""

from __future__ import annotations

from config.celery import app

from apps.compliance.models import System
from apps.risk.services import recalcular
from engines.risk_engine import CicloDetectado


@app.task(name="risk.recalcular")
def recalcular_riesgo(system_id: int) -> dict:
    """Recalcula los riesgos de un sistema.

    Un ciclo en el grafo **no es un error del sistema**: es un fallo de modelado del
    cliente. Se devuelve como resultado con los activos implicados para que la pantalla
    lo enseñe, en vez de dejar la tarea en rojo sin explicación.
    """
    system = System.objects.get(pk=system_id)
    try:
        calculados = recalcular(system)
    except CicloDetectado as error:
        return {"estado": "CICLO", "ciclo": list(error.ciclo), "mensaje": str(error)}
    return {"estado": "OK", "riesgos": calculados}
