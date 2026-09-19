# BLENS

Plataforma SaaS para cumplir el **Esquema Nacional de Seguridad** (RD 311/2022).

La fuente de verdad del producto es [`CLAUDE.md`](CLAUDE.md); el plan por fases está en
[`docs/plan_construccion.md`](docs/plan_construccion.md). Este README solo explica cómo
levantar el entorno.

## Requisitos

- [uv](https://docs.astral.sh/uv/) (Python 3.13)
- Node 20 y pnpm 9
- Docker (Postgres y Redis de desarrollo)

## Puesta en marcha

```bash
cp .env.example .env          # ajusta lo que necesites
docker compose up -d          # Postgres 5434 · Redis 6381
uv sync
uv run backend/manage.py migrate
uv run backend/manage.py runserver 8001
```

En otra terminal:

```bash
pnpm --dir frontend install
pnpm --dir frontend dev       # http://localhost:5175
```

**Puertos no estándar a propósito**, para convivir con otros proyectos: Postgres `5434`,
Django `8001`, Vite `5175`, Redis `6381`.

El frontend **no comparte origen con la API**: llega a ella por el proxy de Vite. Django
solo acepta escrituras con sesión desde los orígenes de `DJANGO_CSRF_TRUSTED_ORIGINS`
(ver `.env.example`); si cambias el puerto de Vite, cámbialo también ahí o toda escritura
se quedará en un 403.

## Comandos

```bash
uv run pytest                                  # tests de backend y motores
uv run ruff check . && uv run black --check .  # estilo
uv run backend/manage.py makemigrations        # migraciones
cd backend && uv run celery -A config worker   # worker (ver nota de WeasyPrint)

pnpm --dir frontend test                       # vitest
pnpm --dir frontend build                      # typecheck + build
pnpm --dir frontend gen:api                    # OpenAPI → tipos TS (no se escriben a mano)

# Validación del seed contra el catálogo OSCAL oficial (se ejecuta en CI)
uv run python db/seed/blens/validate_seed.py db/seed/oscal/ENS_Anexo_II_rev_9.json

# Catálogo a base de datos: primero el OSCAL oficial, después la capa MAGERIT
uv run backend/manage.py import_ens_oscal db/seed/oscal/ENS_Anexo_II_rev_9.json
uv run backend/manage.py seed_magerit     # repetirlo tras cada import: el mapa cuelga de las medidas

# Cobertura de los motores (el plan exige el 100 %)
uv run pytest engines --cov=engines.risk_engine --cov=engines.scoring_engine --cov-report=term-missing
```

## Estructura

| Carpeta | Qué hay |
|---|---|
| `backend/` | Django + Django Ninja. `config/` (proyecto), `apps/` (dominio), `api/` (routers y esquemas) |
| `engines/` | Motores Python **puros**, sin Django: riesgo, scoring, evidencias, aplicabilidad, OSCAL, CPSTIC |
| `frontend/` | Vue 3 + Vite + TypeScript, Pinia y Vue Router |
| `db/seed/` | Catálogo OSCAL oficial (sin tocar) y la capa propia de BLENS |
| `design/` | Handoff visual: manda en lo visual sobre cualquier otra referencia |
| `infra/` | AWS CDK en Python (eu-west-1) |

## Generación de PDF (WeasyPrint)

WeasyPrint necesita pango y cairo del sistema. En macOS, además de instalarlos, hay que
indicarle dónde están: Homebrew los deja en `/opt/homebrew/lib`, que dyld no mira por
defecto. Y el pool `prefork` de Celery no funciona bien con fork en macOS, así que en
local se usa `--pool=solo`:

```bash
brew install pango cairo gdk-pixbuf libffi
cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
  uv run celery -A config worker -l info --pool=solo
```

En Linux (y en el contenedor de producción) no hace falta ninguna de las dos cosas.

## Base de datos de desarrollo

El contenedor sirve la base **`blens_dev`**.

## Flujo de trabajo

Rama por fase o cambio (`f0-cimientos`, `f1-...`), commits pequeños y PR. Nunca push
directo a `main`.
