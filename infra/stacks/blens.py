"""Pila principal. Vacía en F0 (ver `infra/app.py`)."""

import aws_cdk as cdk
from constructs import Construct


class BlensStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        # Los recursos llegan cuando toque desplegar. Ver el docstring de app.py.
