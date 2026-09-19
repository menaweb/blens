#!/usr/bin/env python
"""Punto de entrada de la infraestructura (AWS CDK en Python, §5).

En F0 solo existe el andamiaje: la pila está vacía a propósito. Lo que irá aquí,
siempre en **eu-west-1** (§5, residencia del dato en la UE):

- Aurora PostgreSQL multi-AZ.
- S3 con versioning + Object Lock y cifrado SSE-KMS (§11).
- ECS Fargate para el backend y el worker de Celery; SQS como broker.
- CloudFront + S3 para el frontend estático.
- Cognito con MFA, WAF, GuardDuty, Security Hub, Config y Secrets Manager (§13).

Las dependencias de CDK no se instalan por defecto:  uv sync --group infra
"""

import aws_cdk as cdk
from stacks.blens import BlensStack

app = cdk.App()
BlensStack(
    app,
    "Blens",
    env=cdk.Environment(region="eu-west-1"),
    description="BLENS — plataforma de cumplimiento del ENS",
)
app.synth()
