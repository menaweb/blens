"""Ayudas para los tests de API. No se importa desde el producto.

Existe para que ningún test invente su propia forma de autenticarse: todos piden el
token por el mismo camino que una persona, contra el doble en memoria del proveedor de
identidad (D1: la CI no llama a AWS).
"""

from __future__ import annotations

from django.test import Client

from apps.tenancy.identity import get_identity

#: Contraseña de las cuentas de prueba. Cumple la política del doble (12 caracteres).
PASSWORD = "contrasena-de-prueba"


def token_de(usuario) -> str:
    resultado = get_identity().iniciar_sesion(usuario.username, PASSWORD)
    assert (
        not resultado.pendiente_mfa
    ), "El proveedor pidió segundo factor: este usuario necesita pasar por mfa/challenge."
    return resultado.access_token


def como(usuario) -> Client:
    """Cliente autenticado como ese usuario, con `Authorization: Bearer`."""
    return Client(HTTP_AUTHORIZATION=f"Bearer {token_de(usuario)}")
