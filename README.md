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

## Comandos

```bash
uv run pytest                                  # tests de backend y motores
uv run ruff check . && uv run black --check .  # estilo
uv run backend/manage.py makemigrations        # migraciones
uv run celery -A config worker -l info         # worker (desde backend/)

pnpm --dir frontend test                       # vitest
pnpm --dir frontend build                      # typecheck + build
pnpm --dir frontend gen:api                    # OpenAPI → tipos TS (no se escriben a mano)

# Validación del seed contra el catálogo OSCAL oficial (se ejecuta en CI)
uv run python db/seed/blens/validate_seed.py db/seed/oscal/ENS_Anexo_II_rev_9.json
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

## Base de datos de desarrollo

El contenedor sirve la base **`blens_dev`**.

## Flujo de trabajo

Rama por fase o cambio (`f0-cimientos`, `f1-...`), commits pequeños y PR. Nunca push
directo a `main`.
