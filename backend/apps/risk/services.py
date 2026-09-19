"""Puente entre la base de datos y `engines.risk_engine` (M7).

El motor es puro y no conoce Django (§15): aquí se traduce el inventario del cliente a
sus estructuras, se ejecuta el análisis y se guarda la foto. Ni una fórmula vive en este
módulo; si alguna se cuela, está en el sitio equivocado.

**El acoplamiento riesgo↔cumplimiento se cierra aquí**: la eficacia de cada salvaguarda
sale de `MeasureAssessment`, la misma fila que alimenta el índice de cumplimiento. No hay
una segunda madurez que mantener.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from apps.catalog.models import (
    CatalogVersion,
    MageritThreat,
    MaturityEffectiveness,
    MeasureThreatMap,
)
from apps.compliance.models import MeasureAssessment
from apps.risk.models import Asset, AssetDependency, RiskResult, ThreatInstance
from engines.risk_engine import (
    Activo,
    Amenaza,
    Analisis,
    Dependencia,
    Salvaguarda,
    agregar_por_activo,
    analizar,
    simular,
)

__all__ = [
    "agregar_por_activo",
    "analizar_sistema",
    "amenazas_por_defecto",
    "recalcular",
    "simular_instancia",
]


def _activos(system) -> list[Activo]:
    return [
        Activo(
            id=str(activo.pk),
            valores={v.dim: Decimal(v.own_value) for v in activo.valoraciones.all()},
        )
        for activo in Asset.objects.filter(system=system).prefetch_related("valoraciones")
    ]


def _dependencias(system) -> list[Dependencia]:
    return [
        Dependencia(parent=str(dep.parent_id), child=str(dep.child_id), degree=Decimal(dep.degree))
        for dep in AssetDependency.objects.filter(parent__system=system)
    ]


def _amenazas(system) -> list[Amenaza]:
    return [
        Amenaza(
            asset_id=str(fila.asset_id),
            threat_id=fila.threat.code,
            dim=fila.dim,
            frequency=Decimal(fila.frequency),
            degradation=Decimal(fila.degradation),
        )
        for fila in ThreatInstance.objects.filter(asset__system=system).select_related("threat")
    ]


def _salvaguardas(system, version: CatalogVersion) -> list[Salvaguarda]:
    """Mapa medida↔amenaza × madurez declarada. Lo que no está valorado no reduce nada."""
    valoraciones = {
        fila.measure_id: fila
        for fila in MeasureAssessment.objects.filter(system=system).select_related("measure")
    }
    salida = []
    for fila in MeasureThreatMap.objects.filter(catalog=version).select_related(
        "measure", "threat"
    ):
        valoracion = valoraciones.get(fila.measure_id)
        # Sin valorar o marcada como no aplicable, la medida no cuenta como salvaguarda:
        # el riesgo residual no se apoya en algo que el cliente no ha declarado.
        if valoracion is None or not valoracion.applies or valoracion.maturity_level is None:
            continue
        salida.append(
            Salvaguarda(
                threat_id=fila.threat.code,
                measure_id=fila.measure.code,
                aspect=fila.aspect,
                weight=Decimal(fila.weight),
                nivel=valoracion.maturity_level,
                dim=fila.dim or None,
                soportada=valoracion.madurez_soportada,
            )
        )
    return salida


def tabla_de_eficacia() -> dict[int, Decimal]:
    tabla = MaturityEffectiveness.tabla()
    if not tabla:
        raise RuntimeError(
            "Falta la tabla de eficacia por madurez. Ejecuta el comando seed_magerit."
        )
    return tabla


def analizar_sistema(system, version: CatalogVersion | None = None) -> Analisis:
    """Ejecuta el análisis completo. Levanta `CicloDetectado` si el grafo tiene ciclos."""
    version = version or CatalogVersion.current()
    return analizar(
        activos=_activos(system),
        dependencias=_dependencias(system),
        amenazas=_amenazas(system),
        salvaguardas=_salvaguardas(system, version),
        eficacia_por_nivel=tabla_de_eficacia(),
    )


@transaction.atomic
def recalcular(system, version: CatalogVersion | None = None) -> int:
    """Recalcula y reescribe los `RiskResult` del sistema. Devuelve cuántos.

    Se reescriben enteros en lugar de ir casando diferencias: el resultado es una foto
    con su `computed_at`, no un dato editable, y así no queda ningún residuo de una
    amenaza que el cliente haya borrado.
    """
    instancias = {
        (str(fila.asset_id), fila.threat.code, fila.dim): fila
        for fila in ThreatInstance.objects.filter(asset__system=system).select_related("threat")
    }
    RiskResult.objects.filter(threat_instance__asset__system=system).delete()
    if not instancias:
        # Sin amenazas declaradas no hay nada que calcular. Se sale antes de pedir la
        # tabla de eficacia: un sistema que todavía no ha hecho su análisis de riesgos
        # no tiene por qué fallar cada vez que alguien toca una madurez en el checklist.
        return 0

    analisis = analizar_sistema(system, version)

    filas = []
    for riesgo in analisis.riesgos:
        instancia = instancias[(riesgo.asset_id, riesgo.threat_id, riesgo.dim)]
        filas.append(
            RiskResult(
                threat_instance=instancia,
                accumulated_value=riesgo.valor_acumulado,
                intrinsic_risk=riesgo.riesgo_intrinseco,
                residual_freq_factor=riesgo.factor_freq,
                residual_impact_factor=riesgo.factor_impacto,
                residual_risk=riesgo.riesgo_residual,
                salvaguardas=[
                    {
                        "measure": aportacion.measure_id,
                        "aspect": aportacion.aspect,
                        "weight": str(aportacion.weight),
                        "nivel": aportacion.nivel,
                        "eficacia": str(aportacion.eficacia),
                        "soportada": aportacion.soportada,
                    }
                    for aportacion in riesgo.salvaguardas
                ],
            )
        )
    RiskResult.objects.bulk_create(filas)
    return len(filas)


def amenazas_por_defecto(asset: Asset) -> int:
    """Propone las amenazas del catálogo que encajan con el tipo de activo.

    Crea la instancia con los valores por defecto del seed, que son **un punto de
    partida**: el análisis vale por lo que el cliente ajusta después. No pisa lo que ya
    exista, porque ese ajuste es suyo.
    """
    version = asset.asset_type.catalog
    tipo = asset.asset_type.code
    raiz = tipo.split(".")[0]
    creadas = 0
    for amenaza in MageritThreat.objects.filter(catalog=version).prefetch_related(
        "valores_por_defecto"
    ):
        if tipo not in amenaza.aplica_a and raiz not in amenaza.aplica_a:
            continue
        for defecto in amenaza.valores_por_defecto.all():
            _, creada = ThreatInstance.objects.get_or_create(
                asset=asset,
                threat=amenaza,
                dim=defecto.dim,
                defaults={
                    "tenant": asset.tenant,
                    "frequency": defecto.default_frequency,
                    "degradation": defecto.default_degradation,
                },
            )
            creadas += int(creada)
    return creadas


def simular_instancia(instancia: ThreatInstance, objetivo: Decimal, version=None):
    """Simulador inverso sobre una instancia concreta (§9.4)."""
    version = version or CatalogVersion.current()
    resultado = getattr(instancia, "resultado", None)
    if resultado is None:
        raise ValueError("Hay que recalcular el riesgo antes de simular sobre él.")
    amenaza = Amenaza(
        asset_id=str(instancia.asset_id),
        threat_id=instancia.threat.code,
        dim=instancia.dim,
        frequency=Decimal(instancia.frequency),
        degradation=Decimal(instancia.degradation),
    )
    propias = [
        s
        for s in _salvaguardas(instancia.asset.system, version)
        if s.threat_id == instancia.threat.code and (s.dim is None or s.dim == instancia.dim)
    ]
    return simular(
        amenaza=amenaza,
        valor_acumulado=Decimal(resultado.accumulated_value),
        salvaguardas=propias,
        eficacia_por_nivel=tabla_de_eficacia(),
        objetivo=objetivo,
    )
