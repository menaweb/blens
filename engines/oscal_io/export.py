"""Export de la Declaración de Aplicabilidad a OSCAL.

**Modelo elegido: `profile`** (§17 lo dejaba abierto entre profile y SSP). Una DdA dice
qué controles del catálogo aplican, cuáles no y qué opción se ha elegido donde la norma
da a elegir: eso es exactamente lo que un Profile expresa con `include-controls`,
`exclude-controls` y `set-parameters`. Un SSP describiría además *cómo* está implementado
cada control, que es información de la madurez y de las evidencias, no de la DdA. Cuando
haga falta publicar la implementación, se añadirá un SSP que importe este profile.

Determinista: mismo input, mismo fichero (el uuid sale de un uuid5 del sistema y la
versión). Sin Django ni I/O: recibe datos y devuelve un dict.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

#: Espacio de nombres propio para que los uuid de una misma DdA no cambien entre exports.
NAMESPACE_BLENS = uuid.UUID("6f1b6c4e-6b8f-5c3a-9d2e-b1e450000001")
NS_ENS = "urn:es:ens"


@dataclass(frozen=True)
class DecisionMedida:
    """Lo que la DdA decide sobre una medida."""

    measure_id: str
    aplica: bool
    motivo: str = ""
    justificacion: str = ""
    compensatoria: str = ""
    refuerzos: tuple[str, ...] = ()
    #: {param_id: refuerzo elegido}
    selecciones: dict[str, str] = field(default_factory=dict)


def dda_to_oscal_profile(
    *,
    organizacion: str,
    sistema: str,
    version: int,
    categoria: str,
    niveles: dict[str, str],
    catalogo_href: str,
    catalogo_version: str,
    fecha: str,
    decisiones: list[DecisionMedida],
    aprobador: str = "",
) -> dict:
    """Devuelve la DdA como un OSCAL Profile 1.1.3, listo para serializar a JSON."""
    identificador = uuid.uuid5(NAMESPACE_BLENS, f"{organizacion}|{sistema}|dda|{version}")

    incluidos: list[str] = []
    excluidos: list[str] = []
    set_parameters: list[dict] = []
    justificaciones: list[str] = []

    for decision in sorted(decisiones, key=lambda d: d.measure_id):
        if decision.aplica:
            incluidos.append(decision.measure_id)
            incluidos.extend(sorted(decision.refuerzos))
            for param_id, elegido in sorted(decision.selecciones.items()):
                if elegido:
                    set_parameters.append({"param-id": param_id, "values": [elegido]})
        else:
            excluidos.append(decision.measure_id)
            if decision.justificacion:
                justificaciones.append(f"{decision.measure_id}: {decision.justificacion}")
            if decision.compensatoria:
                justificaciones.append(
                    f"{decision.measure_id} (compensatoria): {decision.compensatoria}"
                )

    props = [{"ns": NS_ENS, "name": "categoria", "value": categoria}]
    props += [
        {"ns": NS_ENS, "name": "nivel", "value": nivel, "class": dimension}
        for dimension, nivel in sorted(niveles.items())
    ]

    metadata = {
        "title": f"Declaración de Aplicabilidad · {sistema}",
        "last-modified": fecha,
        "version": str(version),
        "oscal-version": "1.1.3",
        "props": props,
        "parties": [
            {
                "uuid": str(uuid.uuid5(NAMESPACE_BLENS, organizacion)),
                "type": "organization",
                "name": organizacion,
            }
        ],
        "remarks": (
            "Generada por BLENS a partir del catálogo OSCAL del Anexo II del RD 311/2022. "
            "Las medidas excluidas llevan su justificación en los remarks del import."
        ),
    }
    if aprobador:
        metadata["props"].append({"ns": NS_ENS, "name": "aprobador", "value": aprobador})

    importacion: dict = {
        "href": catalogo_href or f"#{catalogo_version}",
        "include-controls": [{"with-ids": incluidos}],
    }
    if excluidos:
        importacion["exclude-controls"] = [{"with-ids": excluidos}]
    if justificaciones:
        importacion["remarks"] = "\n".join(justificaciones)

    profile: dict = {
        "profile": {
            "uuid": str(identificador),
            "metadata": metadata,
            "imports": [importacion],
            "merge": {"as-is": True},
        }
    }
    if set_parameters:
        profile["profile"]["modify"] = {"set-parameters": set_parameters}
    return profile
