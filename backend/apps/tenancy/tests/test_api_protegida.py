"""Ningún endpoint se queda sin autenticación por descuido.

Criterio de cierre de F3b: esto recorre el OpenAPI entero y **falla cuando alguien añade
un router nuevo sin declarar `auth`**. La lista blanca de abajo es la única puerta
abierta, y ampliarla obliga a pasar por aquí y a explicar por qué.
"""

from api.urls import api

#: Lo público, con su motivo. Si algo entra aquí, es una decisión, no un olvido.
PUBLICOS = {
    # Sonda de infraestructura.
    ("GET", "/api/health"),
    # Alta y recuperación: por definición, antes de tener sesión.
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/confirm"),
    ("POST", "/api/auth/resend"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/mfa/challenge"),
    ("POST", "/api/auth/refresh"),
    ("POST", "/api/auth/password/forgot"),
    ("POST", "/api/auth/password/reset"),
    # Quien acepta una invitación todavía no tiene cuenta; el token es su credencial.
    ("GET", "/api/auth/invitation/{token}"),
    ("POST", "/api/auth/invitation/{token}/accept"),
    # El catálogo del ENS es norma publicada: dato de referencia, no de nadie.
    ("GET", "/api/catalog/versions"),
    ("GET", "/api/catalog/measures"),
    ("GET", "/api/catalog/measures/{code}"),
    ("POST", "/api/catalog/applicability"),
    ("GET", "/api/catalog/dimensiones"),
    # M1 es el gancho: se usa sin cuenta a propósito (§4). Lo que guarda caduca.
    ("POST", "/api/categorization/preview"),
    ("POST", "/api/categorization/report"),
    ("GET", "/api/categorization/report/{token}"),
    ("GET", "/api/categorization/report/{token}/pdf"),
    ("GET", "/api/categorization/vocabulario"),
}


def _sin_autenticacion() -> set[tuple[str, str]]:
    api.urls  # noqa: B018 — construye las rutas, que es cuando se resuelve el `auth`
    esquema = api.get_openapi_schema()
    return {
        (metodo.upper(), ruta)
        for ruta, operaciones in esquema["paths"].items()
        for metodo, operacion in operaciones.items()
        if not operacion.get("security")
    }


def test_solo_es_publico_lo_que_esta_en_la_lista():
    nuevos = _sin_autenticacion() - PUBLICOS

    assert not nuevos, (
        "Estos endpoints no piden autenticación y no están en la lista blanca. "
        "Si es a propósito, añádelos ahí con su motivo; si no, ponles `auth`: "
        f"{sorted(nuevos)}"
    )


def test_la_lista_blanca_no_se_queda_con_rutas_muertas():
    """Una entrada que ya no existe es ruido que tapa el siguiente descuido."""
    sobran = PUBLICOS - _sin_autenticacion()

    assert not sobran, f"Ya no existen o ya piden autenticación: {sorted(sobran)}"


def test_todo_lo_demas_pide_token(db, anonimo):
    """Comprobación de verdad, no solo de esquema, sobre una muestra de cada router."""
    for ruta in (
        "/api/systems",
        "/api/members",
        "/api/auth/me",
        "/api/me/activity",
    ):
        assert anonimo.get(ruta).status_code == 401, ruta
