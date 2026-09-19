# Dónde va cada fichero en el repositorio

Descomprime el ZIP en la raíz del repositorio `blens/`. La estructura ya coincide,
salvo dos ficheros sueltos que hay que colocar (ver abajo).

```
blens/
  CLAUDE.md                    ← fuente de verdad, en la raíz
  docs/
    plan_construccion.md       ← fases y prompts para Claude Code
    brief_diseno.md            ← diseño (referencia a otros docs)
    brief_diseno_standalone.md ← el que se le pasa a Claude Design
    cuestionario_perfilado.md
    evidencias_por_herramienta.md
    competencia_y_ux.md
    roles_y_permisos.md
    decisiones.md
    validacion_externa.md
    ingesta_ia.md
  db/seed/
    oscal/                     ← ⚠️ CREAR: aquí va el JSON oficial del Anexo II (sin tocar)
    blens/
      validate_seed.py         ← validador, se ejecuta en CI
      questions.*.yaml         (7 ficheros, 151 preguntas)
      evidence_templates.*.yaml (7 ficheros, 196 plantillas)
      magerit/                 (tipos de activo, 50 amenazas, 269 pares medida-amenaza)
      checks/                  (16 familias, 464 checks + los dos generadores)
  engines/cpstic_parser/       ← ⚠️ COLOCAR AQUÍ: cpstic_parser_prototipo.py
  design/
    README_handoff.md          ← especificación visual (manda en lo visual)
    prototipos/                ← 18 .dc.html + support.js (referencia, no producción)
```

## Antes de arrancar

1. Descarga el JSON del Anexo II en OSCAL desde el PAe y déjalo en `db/seed/oscal/`, **sin editarlo**.
2. Mueve `cpstic_parser_prototipo.py` a `engines/cpstic_parser/` (es un prototipo, se reescribe en la fase F7).
3. Comprueba que el seed valida:
   ```
   python db/seed/blens/validate_seed.py db/seed/oscal/<fichero>.json
   ```
   Debe terminar con `RESULTADO: OK`.

## Primer prompt para Claude Code

> Lee `CLAUDE.md` completo y `docs/plan_construccion.md`. Ejecuta la fase F0:
> estructura del monorepo, Django + Django Ninja con OpenAPI, apps vacías, Celery con SQS,
> uv, frontend Vue 3 + Vite con generación de tipos desde el OpenAPI, CI con ruff, black,
> pytest y vitest, y los modelos de roles y permisos de `docs/roles_y_permisos.md`.
> No implementes lógica de negocio todavía. Respeta §5 (stack fijado) y §15 (convenciones).
> Pregunta antes de introducir cualquier dependencia que no esté en §5.

Los prompts de las fases siguientes están en `docs/plan_construccion.md`, uno por fase.

## Cuando toque construir la interfaz

> Lee `CLAUDE.md` y `design/README_handoff.md`. Implementa la pantalla «Perfilado, ficha de
> pregunta» en Vue 3 siguiendo las convenciones de `CLAUDE.md` y la especificación visual del
> handoff. Antes de escribir código, dime qué tokens mapeas y qué componentes reutilizables vas
> a crear. Los `.dc.html` son referencia: no copies su HTML ni sus estilos en línea.
