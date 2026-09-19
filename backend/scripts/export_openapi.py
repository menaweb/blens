#!/usr/bin/env python
"""Vuelca el esquema OpenAPI a un fichero, sin levantar el servidor.

Es lo que consume `pnpm --dir frontend gen:api` para generar los tipos TS, y lo que
permite que CI compruebe el contrato sin arrancar Django en modo servidor.
"""

import json
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from api.urls import api  # noqa: E402


def main() -> None:
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    esquema = json.dumps(api.get_openapi_schema(), indent=2, ensure_ascii=False)
    if destino:
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(esquema + "\n", encoding="utf-8")
        print(f"OpenAPI escrito en {destino}")
    else:
        print(esquema)


if __name__ == "__main__":
    main()
