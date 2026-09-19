# Plan de construcción por fases — para Claude Code

> Documento compañero de `CLAUDE.md`. Cada fase tiene **entregables, criterios de cierre y un prompt de arranque** para pegar en Claude Code. Regla general: **no se empieza una fase sin cerrar la anterior**, y los motores van antes que la UI. Lee siempre `CLAUDE.md` completo y los documentos citados antes de escribir código.

## Orden y dependencias

```
F0 Cimientos ──► F1 Catálogo + aplicabilidad ──► F2 Categorización y DdA
                                                      │
                        F3 Motores (scoring + riesgo) ◄┘
                                                      │
       F4 Perfilado y evidencias ◄─────────────────────┘
                     │
       F5 Documental y versionado
                     │
       F6 Paquete de auditoría y portal del auditor ──► fin de la v1
                     │
       GATE producción (aislamiento de tenant, §14.3)
                     │
       F7 CPSTIC ·  F8 Palancas (IA, multimarco, trust center)
```

CPSTIC (F7) puede adelantarse si aparece pronto un cliente en Media o Alta, pero **no bloquea la v1**.

---

## F0 · Cimientos

**Entregables**
- Monorepo según `CLAUDE.md` §6: `backend/` (Django + Django Ninja), `engines/`, `frontend/` (Vue 3 + Vite), `infra/` (CDK Python), `db/seed/`.
- `pyproject.toml` con uv; `pnpm` en frontend; pre-commit con ruff y black.
- Django con apps vacías: `catalog`, `tenancy`, `compliance`, `profiling`, `documents`, `evidence`, `risk`.
- Django Ninja montado con OpenAPI y un endpoint de salud.
- Celery con broker SQS (en local, LocalStack o Redis) y una tarea de prueba.
- PostgreSQL en Docker para desarrollo; Aurora queda para infra.
- CI: ruff, black, pytest, vitest, build del frontend.
- `tenant_id` nullable en los modelos base de tenant desde la primera migración (§14.2).
- **Roles y permisos** (`docs/roles_y_permisos.md`): `Membership`, `Invitation`, `AuditLog` y el punto único `can(user, accion, objeto)`, con las reglas de separación de funciones.

**Cierre**
- [ ] `uv run pytest` y `pnpm --dir frontend build` verdes en CI.
- [ ] `/api/health` responde y el OpenAPI se genera.
- [ ] `pnpm --dir frontend gen:api` produce tipos TS desde el OpenAPI.
- [ ] Tests de `can()`: un Técnico no puede validar evidencias ni aprobar documentos; quien sube una evidencia no puede validarla aunque sea RSEG.

**Prompt de arranque**
> Lee `CLAUDE.md` completo. Crea el andamiaje del monorepo de la fase F0 de `docs/plan_construccion.md`: estructura de carpetas, Django + Django Ninja con OpenAPI, apps vacías, Celery con SQS, uv, frontend Vue 3 + Vite con generación de tipos desde OpenAPI, y CI con ruff, black, pytest y vitest. No implementes lógica de negocio todavía. Respeta §5 (stack fijado) y §15 (convenciones). Pregunta antes de introducir cualquier dependencia que no esté en §5.

---

## F1 · Catálogo ENS y motor de aplicabilidad

**Entregables**
- `engines/oscal_io`: parser del Catalog OSCAL 1.1.3 (puro, sin Django).
- Modelos de `catalog` según §7.1: `CatalogVersion`, `EnsMeasure`, `EnsRefuerzo`, `EnsSelectionParam`, `EnsRequirementItem`.
- Comando `import_ens_oscal`: idempotente, valida contra esquema, guarda JSON original y su sha256, y **falla con informe** si una actualización deja huérfana una referencia de la capa propia.
- `engines/ens_applicability`: dada categoría + niveles por dimensión + catálogo, devuelve medidas y refuerzos aplicables, opcionales y selecciones pendientes. Puro y con pytest.
- Endpoints de consulta del catálogo.

**Cierre**
- [ ] El import carga 73 medidas, 133 refuerzos y 467 items del fichero oficial.
- [ ] Tests de `ens_applicability` con los cuatro perfiles tipo de `docs/cuestionario_perfilado.md` §5.
- [ ] Test que comprueba que mp.info.3 aplica por nivel de Integridad y Autenticidad, no por categoría.
- [ ] Reimportar la misma versión no duplica nada.

**Prompt de arranque**
> Lee `CLAUDE.md` §3, §3.1 y §7.1. Implementa la fase F1 de `docs/plan_construccion.md`: `engines/oscal_io`, los modelos de catálogo, el comando `import_ens_oscal` y `engines/ens_applicability` con pytest. El JSON oficial está en `db/seed/oscal/` y no se edita. Los ids OSCAL son la clave estable. La aplicabilidad no se guarda en tabla: se deriva. Ojo con los 41 refuerzos sin props de aplicabilidad (se tratan como opcionales) y con los 4 params de selección de refuerzo.

---

## F2 · Categorización y Declaración de Aplicabilidad

**Entregables**
- `System`, `DimensionValuation` (nivel por dimensión), categorización del Anexo I.
- M1: cuestionario de 5 dimensiones con ejemplos guiados, **usable sin registro**, con resultado y export PDF.
- M2: `DeclaracionAplicabilidad` y `MeasureApplied` generados con `ens_applicability`; no aplicables con justificación obligatoria; resolución de las selecciones de refuerzo; versionable y aprobable.
- Export de la DdA en PDF y en OSCAL.
- WeasyPrint en el worker Celery, nunca en la petición web.

**Cierre**
- [ ] Categorizar en 2 minutos sin cuenta y descargar el PDF.
- [ ] La DdA se genera para Básica, Media y Alta (diferenciador frente a AMPARO).
- [ ] No se puede aprobar una DdA con selecciones sin resolver o no aplicables sin justificar.

**Prompt de arranque**
> Lee `CLAUDE.md` §4 (M1, M2), §7.2 y §12. Implementa la fase F2. La categorización guarda el nivel de **cada dimensión**, no solo la categoría. La DdA sale de `ens_applicability` y obliga a resolver los params de selección. La generación de PDF va en Celery con WeasyPrint. M1 funciona sin registro.

---

## F3 · Motores de scoring y riesgo

**Entregables**
- `engines/scoring_engine`: L0-L5 a porcentaje, objetivo por categoría, delta, semáforo, composición por el peor componente, índices por familia, marco y sistema.
- `engines/risk_engine`: propagación en el DAG, riesgo intrínseco, residual acoplado a la madurez, agregación y simulador inverso.
- `MeasureAssessment` como fuente única de madurez.
- Modelos de riesgo: `Asset`, `AssetValuation`, `AssetDependency`, `ThreatInstance`, `RiskResult`, `RiskTreatment`.
- M4: checklist de medidas con madurez, responsable, fecha y notas.
- Seed MAGERIT: tipos de activo, amenazas, valores por defecto y `measure_threat_map`.

**Cierre**
- [ ] **Test de regresión de §9.3 obligatorio**: riesgo residual ≈ 3.82 con tolerancia ±0.01.
- [ ] Todo en `Decimal`, con redondeo explícito y almacenado en `NUMERIC`.
- [ ] Ciclos en el grafo detectados y rechazados con mensaje claro.
- [ ] Cambiar una madurez cambia el riesgo residual y el índice de cumplimiento en un solo paso.
- [ ] Cobertura de tests del 100 % en ambos motores.

**Prompt de arranque**
> Lee `CLAUDE.md` §8 y §9 al completo. Implementa la fase F3: `engines/scoring_engine` y `engines/risk_engine` como paquetes Python puros, deterministas, en `Decimal` y con pytest, **antes de cablear nada a Django**. El ejemplo trabajado de §9.3 es test de regresión obligatorio. Después conecta `MeasureAssessment` como fuente única de madurez y expón los endpoints. No dupliques la madurez en ningún otro modelo.

---

## F4 · Perfilado y carpeta de evidencias

**Entregables**
- `engines/evidence_engine`: hechos + categoría + niveles + DdA + plantillas → requisitos. Puro y con pytest.
- Modelos: `ProfileQuestion`, `ProfileOption`, `ProfileAnswer`, `ProfileFact`, `EvidenceTemplate`, `ProductEvidenceHint`, `EvidenceRequirement`, `Evidencia`, `SecurityComponent`.
- Motor de reglas JSON Logic para `show_if` y `applies_if`, compartido entre backend y frontend.
- M11: cuestionario adaptativo con las reglas de redacción de `docs/cuestionario_perfilado.md` §1bis, delegación por bloques y botón "preguntárselo a otra persona".
- M5: carpeta pre-estructurada, grupos de opciones de evidencia, criterios de aceptación, rechazos típicos, subida a S3 con versioning y Object Lock, revisión y caducidad por evidencia.
- Seed completo de las 16 familias (op.exp ya está hecho como formato de referencia).
- Validación del seed en CI (§15).

**Cierre**
- [ ] Cada medida aplicable tiene al menos una plantilla alcanzable desde algún camino.
- [ ] Recalcular tras cambiar una respuesta no borra evidencias: las sobrantes pasan a `FUERA_DE_ALCANCE`.
- [ ] Una evidencia satisface un grupo de opciones y cierra el requisito.
- [ ] Una misma evidencia se enlaza a varios requisitos.
- [ ] Madurez sin evidencia validada se marca como "no soportada".
- [ ] **Validación externa hecha** (`docs/validacion_externa.md`): sesión con un auditor ENAC y un piloto con dos clientes tipo, con el seed corregido a partir de lo que digan.

**Prompt de arranque**
> Lee `CLAUDE.md` §10bis y los documentos `docs/cuestionario_perfilado.md` y `docs/evidencias_por_herramienta.md`. Implementa la fase F4. El seed de op.exp en `db/seed/blens/` es el formato de referencia: replícalo para las demás familias solo cuando yo te pase el contenido; ahora implementa el motor, los modelos, el importador de seed y su validación en CI. Las reglas son datos en JSON Logic, nunca código. `evidence_engine` es puro y determinista.

---

## F5 · Generación documental y versionado

**Entregables**
- M3: plantillas alineadas con CCN-STIC-804, variables desde el perfilado, salida HTML editable con export a PDF y DOCX.
- M8: `Documento` y `DocumentoVersion` con sha256, S3 versioning y Object Lock, flujo de estados, aprobador, historial y diff.
- M12: publicación de normativa y acuse de lectura con informe de cobertura.
- M13: registro de incidentes y PAC.

**Cierre**
- [ ] Un documento recorre el flujo completo hasta `VIGENTE` y su versión anterior queda `OBSOLETO` y consultable.
- [ ] El sha256 almacenado coincide con el objeto de S3.
- [ ] El acuse de lectura genera por sí solo la evidencia de org.2 y mp.per.2.

**Prompt de arranque**
> Lee `CLAUDE.md` §4 (M3, M8, M12, M13) y §11. Implementa la fase F5. Generación y render siempre en Celery. Inmutabilidad real: S3 versioning más Object Lock más sha256 por versión. El acuse de lectura debe producir evidencia enlazable a requisitos.

---

## F6 · Paquete de auditoría y portal del auditor (cierre de la v1)

**Entregables**
- M9: ZIP con la estructura de §10, índice navegable HTML, PDF maestro, matriz de evidencias en Excel y trazabilidad pregunta → medida → check → evidencia.
- M14: portal del auditor con acceso por invitación caducable, muestreo, peticiones de información, marcado de revisado y traza inmutable.
- M6: dashboard con el indicador de listo para auditoría y sus tres componentes, heat-map, ranking de gaps y vistas cruzadas riesgo-activo-medida. Export INES.
- Ficha previa para la entidad de certificación (`docs/cuestionario_perfilado.md` §7).

**Cierre**
- [ ] El ZIP se genera en Celery y se descarga con enlace firmado y caducable.
- [ ] El indicador nunca cuenta madurez sin evidencia validada ni redondea al alza.
- [ ] Un auditor invitado ve, muestrea y pide información sin tocar nada.
- [ ] **Validación real: un auditor externo revisa el paquete y dice qué le falta.**

**Prompt de arranque**
> Lee `CLAUDE.md` §10, M9, M14 y M6, más `docs/competencia_y_ux.md` §3 y §4. Implementa la fase F6. El indicador de listo para auditoría se calcula en `scoring_engine`, con sus tres componentes visibles por separado. El portal del auditor es solo lectura, con invitación caducable y traza inmutable de todo lo que hace.

---

## GATE de producción · Aislamiento de tenant

No se expone a clientes reales hasta cerrar entero el §14.3 de `CLAUDE.md`: `tenant_id` NOT NULL, managers scoped por contexto autenticado, RLS de PostgreSQL con `SET LOCAL` dentro de transacción, tests negativos permanentes en CI y revisión de que no hay consultas que salten los managers.

**Prompt de arranque**
> Lee `CLAUDE.md` §14 completo. Implementa el gate de producción. Empieza por los **tests negativos** (un usuario del tenant A no puede leer ni escribir datos del tenant B) y haz que fallen; luego implementa NOT NULL, managers scoped, middleware de contexto y RLS hasta que pasen. Esa suite se queda para siempre.

---

## F7 · CPSTIC

`engines/cpstic_parser` (el prototipo está en `cpstic_parser_prototipo.py`), staging con diff y revisión humana en panel admin, `CpsticSnapshot`, rutas de op.pl.5 en `SecurityComponent`, revalidación mensual y avisos de caducidad. **Antes de producción:** resolver el criterio legal de §3.2.0.

---

## F8 · Palancas (post-v1)

M16 ingesta asistida por IA (`docs/ingesta_ia.md`), mapeo multimarco con reutilización de evidencias, recolectores automáticos por API, riesgo de proveedores, M15 portal de confianza y M10 modo consultora.

---

## Reglas que Claude Code no debe romper

1. **Los motores son puros:** sin Django, sin I/O, deterministas, en `Decimal` y con pytest al 100 %.
2. **El catálogo es dato:** nada de medidas, refuerzos ni reglas escritas en el código.
3. **Una sola fuente de verdad para la madurez:** `MeasureAssessment`.
4. **Trabajo pesado en Celery:** PDF, DOCX, ZIP, parsers y recálculos masivos.
5. **API tipada:** esquemas Pydantic en Django Ninja y tipos TS generados desde el OpenAPI.
6. **Migraciones:** nunca editar una aplicada; añadir una nueva.
7. **Sin secretos en el repo.**
8. **Ante una decisión con coste de reversión alto que no esté en `CLAUDE.md`: preguntar.**
