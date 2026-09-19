"""Motor de aplicabilidad del Anexo II. Puro, sin Django: se deriva, no se guarda."""

from .engine import (
    MedidaAplicable,
    Perfil,
    Resultado,
    SeleccionPendiente,
    aplicabilidad,
    refuerzos_de,
)

__all__ = [
    "MedidaAplicable",
    "Perfil",
    "Resultado",
    "SeleccionPendiente",
    "aplicabilidad",
    "refuerzos_de",
]
