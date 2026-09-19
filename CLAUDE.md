# CLAUDE.md — BLENS

> **Qué es este archivo.** Brief maestro y fuente de verdad para construir **BLENS** con Claude Code. Léelo entero antes de escribir código. Define el producto, el dominio (ENS), el stack, la arquitectura, el modelo de datos, los motores (cumplimiento, riesgos MAGERIT, evidencias, versionado), los módulos, el **alcance de la v1**, el **gate previo a producción** y las convenciones de trabajo. Cuando una decisión no esté aquí, **pregunta antes de asumir** (§15).

---

## Índice
0. **Estado actual del repositorio** — qué existe hoy y qué no
1. Qué es BLENS
2. Usuarios y propuesta de valor
3. Dominio ENS (contexto imprescindible)
4. Alcance del producto — módulos
5. Stack y arquitectura (DECIDIDO)
5bis. **Convenciones de UI/UX (derivadas de la competencia)**
6. Estructura del repositorio
7. Modelo de datos
8. Motor de scoring (madurez / cumplimiento)
9. Motor de análisis de riesgos MAGERIT
10. Motor de evidencias y paquete de auditoría
10bis. **Perfilado del sistema y requisitos de evidencia (eje del producto)**
11. Control de versiones documental
12. Flujos de usuario
13. Requisitos no funcionales
14. **Alcance de la v1 y gate previo a producción**
15. Convenciones para Claude Code
16. Roadmap de construcción
17. Decisiones abiertas

---

## 0. Estado actual del repositorio

> **Léelo antes de creerte §6 y §15.** El producto descrito en este documento está por
> construir; lo que existe hoy es **F0 y F1 cerradas**, más la especificación, el seed y el
> diseño. Nada de la cara de cliente (categorización, DdA, perfilado) está hecho todavía.

**Construido:**

```
F0  backend/   Django 5.2 + Django Ninja. config/ (settings, celery), api/ (routers, OpenAPI),
               apps/tenancy: Tenant, Membership, Invitation, AuditLog encadenado y can()
    frontend/  Vue 3 + Vite + TS, Pinia, Vue Router, Vitest. Tipos generados del OpenAPI
    infra/     CDK en Python: pila vacía, eu-west-1. Deps aparte: uv sync --group infra
    .github/   CI: ruff · black · makemigrations --check · pytest · validate_seed · vitest · build

F1  engines/oscal_io          lee y valida el Catalog OSCAL 1.1.3, y exporta la DdA a
                              OSCAL **profile** (decisión tomada; §17 lo dejaba abierto)
    engines/ens_applicability categoría + niveles por dimensión → medidas, refuerzos y
                              selecciones pendientes (puro, determinista)
    apps/catalog              CatalogVersion, EnsMeasure, EnsRefuerzo, EnsSelectionParam,
                              EnsRequirementItem + import_ens_oscal idempotente
    /api/catalog              versiones, medidas, detalle y applicability (solo lectura)

F2  M1 categorización         DimensionValuation + asistente de 5 pasos **sin cuenta**,
                              con PDF generado en Celery (WeasyPrint) y caducidad de los
                              resultados anónimos · pantalla Vue según el handoff
    M2 DdA                    DeclaracionAplicabilidad + MeasureApplied versionables,
                              aprobación bloqueada si quedan selecciones sin resolver o
                              no aplicables sin justificar · export PDF y OSCAL
```

**Sin construir:** la landing (`landing/`), los motores de riesgo, scoring y evidencias, el
seed a base de datos (`seed_blens`), el parser CPSTIC de verdad (solo hay prototipo) y las
apps `profiling`, `documents`, `evidence` y `risk`. Siguiente fase: **F3** (motores de
scoring y riesgo), en `docs/plan_construccion.md`.

**Puesta en marcha y comandos:** `README.md`. Puertos no estándar a propósito para convivir
con otros proyectos: Postgres **5434**, Django **8001**, Vite **5175**, Redis **6381**.

**Base de datos de desarrollo: `blens_dev`.** Hubo un BLENS anterior (julio de 2026) cuyo
esquema sobrevivía en este Postgres; se borró por decisión expresa. **No se parte de él**:
todo lo anterior a F0 queda descartado.

**Convención de nombres de hechos — no la rompas.** Las claves de `ProfileFact` son **planas
y en snake_case** (`instalacion_cpd`, `entidad_tipo`, `cred_ciclo`). En JSON Logic,
`{var: "hechos.a.b"}` significa *recorrer* `hechos → a → b`, así que un hecho plano llamado
`a.b` **nunca resolvería**. `docs/cuestionario_perfilado.md` sí usa notación con puntos
(`entidad.tipo`, `infra.ubicacion[]`, `nivel.C`): es notación de especificación, y al bajarla
al seed se aplana. Tres condiciones arrastraban la notación del documento y dejaban el seed
en rojo; se corrigieron así:

| Era | Ahora | Cómo |
|---|---|---|
| `hechos.entidad.tipo` | `hechos.entidad_tipo` | nueva pregunta `org.entidad` (bloque **B00**) |
| `hechos.ciclo` (nadie lo emitía) | `hechos.ciclo` | nueva pregunta `org.ciclo` (bloque **B00**) |
| `hechos.infra.ubicacion ∈ [nube, saas, hibrido]` | `hechos.instalacion_externa == true` | ya lo emitía `mp.if.areas` y nadie lo consumía |

**Bloque B00 incompleto a propósito:** solo tiene las dos preguntas de las que dependen
condiciones de otros bloques. El resto de B0 del cuestionario (motivo, alcance, sedes,
volumen, teletrabajo, subcontratación) sigue pendiente para la fase de perfilado.

**Límite conocido de `instalacion_externa`:** su opción es «En instalaciones de un proveedor
o en la nube», así que no distingue *coubicación/hosting* de *nube pública* ni de *SaaS*,
como sí hace B3.1 del cuestionario. Basta para decidir si se muestra el bloque de nube; si
op.nub necesita más finura, se parte esa opción en `mp.if.areas` y se actualizan los
consumidores.

---

## 1. Qué es BLENS

BLENS es una plataforma **SaaS multi-tenant** para cumplir el **Esquema Nacional de Seguridad (ENS)** español. Dos caras sobre un mismo modelo de datos:

- **Producto self-serve.** Lleva al cliente obligado "del desconcierto al cumplimiento, paso a paso": categoriza su sistema, genera su documentación obligatoria, hace seguimiento de medidas, gestiona evidencias y muestra un dashboard. Gancho de adquisición: **categorización gratuita en 2 minutos**.
- **Motor riguroso (por debajo).** Modela las 73 medidas y 133 refuerzos del Anexo II (catálogo OSCAL oficial), calcula madurez L0-L5 (CCN-STIC-815), ejecuta un **análisis de riesgos MAGERIT nativo** (sin PILAR) con las medidas como salvaguardas, versiona documentos de forma inmutable y exporta un **paquete de evidencias en formato auditor ENAC** (mapeado a CCN-STIC-808).

Diferenciador central: **acoplamiento riesgo↔cumplimiento** — la madurez de cada medida alimenta a la vez el índice de cumplimiento y la eficacia de la salvaguarda en el riesgo residual. Una única fuente de verdad.

**Principio rector del producto:** a través de **preguntas**, BLENS aprende cómo es el sistema del cliente (¿CPD propio o en proveedor? ¿qué EDR? ¿cómo hace copias? ¿cómo forma a su personal?) y con ello **plantea una carpeta de documentación y evidencias a medida**, con cada hueco explicado: *qué aportar, por qué lo pide el auditor y cómo debe verse*. El cliente la completa desde la web. **Objetivo final: que el auditor llegue a la auditoría con toda la información lista, trazada y maquetada para auditar.** Ver §10bis.

La landing (`landing/`) será la superficie de captación; la app es lo que hay tras el registro. **Todavía no existe**: el sistema visual se fija en `docs/brief_diseno.md` §2 y la landing se construye después con esos tokens.

---

## 2. Usuarios y propuesta de valor

**Personas:**
- Responsable IT/seguridad de **PYME proveedora** de la Administración (obligada desde 05/2024). Certificarse rápido y barato para no quedar fuera de licitaciones.
- **RSEG de organismo público** (ayuntamiento, universidad…): certificar, mantener, reportar a INES.
- **Consultoras** que acompañan a varios clientes → modo multi-cliente / marca blanca (fase posterior, depende del aislamiento de tenant).

**Promesa:** todo el ENS en un solo sitio. Sin hojas de cálculo, sin Word desactualizado, sin consultoras caras, sin depender de nadie.

---

## 3. Dominio ENS (contexto imprescindible)

- **Norma:** Real Decreto **311/2022** (BOE-A-2022-7191, https://www.boe.es/eli/es/rd/2022/05/03/311). Anexos: I categorías, II medidas, III auditoría, IV glosario. **Es el texto que manda**: el catálogo OSCAL es informativo.
- **Obligaciones del articulado que el producto debe cubrir** (no están en el Anexo II y se olvidan):
  - **Art. 2.3:** el sector privado que presta servicios al público también necesita política de seguridad, aprobada por el órgano con las máximas competencias ejecutivas. Los pliegos deben exigir la Declaración o Certificación de Conformidad y extenderse a la cadena de suministro.
  - **Art. 13.3:** el Responsable de Seguridad es distinto del Responsable del Sistema y **sin dependencia jerárquica**; si no es posible, medidas compensatorias.
  - **Art. 13.5:** los servicios externalizados exigen un **punto de contacto de seguridad** designado por el proveedor.
  - **Art. 14.2:** la metodología de análisis de riesgos debe estar **reconocida internacionalmente**.
  - **Art. 31.1:** auditoría ordinaria **al menos cada dos años**, y extraordinaria ante cambios sustanciales (que reinicia el cómputo). Prórroga de 3 meses solo por fuerza mayor.
  - **Art. 38.2:** hay que **dar publicidad** a la declaración o certificación de conformidad en la web o sede electrónica.
  - **Anexo I:** la categoría se **reevalúa anualmente** o ante cambios significativos.
- **Categorías:** `BASICA`, `MEDIA`, `ALTA`. Se derivan del impacto en 5 dimensiones (**ACIDA**: Autenticidad, Confidencialidad, Integridad, Disponibilidad, Trazabilidad). El nivel de una dimensión en el sistema es **el mayor** de los de cada información y servicio; la categoría, la mayor de las dimensiones. Las dimensiones que no influyen en la categoría **conservan su propio nivel** (Anexo I.4.2): por eso la aplicabilidad se calcula por dimensión, no por categoría.
- **Anexo II — 73 medidas (+133 refuerzos) en 3 marcos y 16 familias** (org cuenta como familia única):

| Marco | Familias | Nº medidas |
|---|---|---|
| Organizativo `[org]` | org | 4 |
| Operacional `[op]` | op.pl, op.acc, op.exp, op.ext, op.nub, op.cont, op.mon | 33 |
| Protección `[mp]` | mp.if, mp.per, mp.eq, mp.com, mp.si, mp.sw, mp.info, mp.s | 36 |

- **Refuerzos:** controles `<medida>.rN`. Pueden ser obligatorios por categoría o por nivel de dimensión, opcionales, o **seleccionables** (elegir uno entre varios: op.acc.5, op.acc.6, mp.com.4, mp.s.2).
- **Dos criterios de aplicabilidad** (no solo categoría):
  - `categoria` → depende de BASICA/MEDIA/ALTA.
  - `nivel-dimension` → depende del nivel (BAJO/MEDIO/ALTO) de dimensiones concretas. Ejemplo: mp.info.3 aplica según el nivel de Integridad/Autenticidad.
  - Por eso **la categorización debe guardar el nivel de cada dimensión**, no solo la categoría resultante.
- **Declaración de Aplicabilidad (DdA):** por medida, si aplica (justificación si no), refuerzos, compensatorias/complementarias. Aprobada por RSEG/Comité. Vinculada al análisis de riesgos.
- **Madurez (CCN-STIC-815):** escala CMM L0-L5. Umbral mínimo: **Básica→L2, Media→L3, Alta→L4**.
- **Conformidad (art. 38):** Básica = **autoevaluación** (puede someterse voluntariamente a certificación); Media y Alta = **certificación** por entidad acreditada, con auditoría al menos bienal (art. 31). El análisis de riesgos es obligatorio (op.pl.1). El ENS **no impone PILAR**: exige metodología reconocida internacionalmente (art. 14.2).
- **Guías:** CCN-STIC-808 (verificación), 809 (declaración/certificación), 815 (madurez), 824/844 (INES). **MAGERIT v3** (metodología pública).

> El catálogo (medidas, refuerzos, checks, mapa de aplicabilidad) es **dato versionado**, desacoplado de los datos del tenant, para actualizar la norma sin romper históricos.

### 3.1 Fuente oficial del catálogo: ENS Anexo II en OSCAL JSON (AEAD, 2026)

**Qué es.** La AEAD publica el Anexo II en **OSCAL 1.1.3 (modelo Catalog)**, versión 1.0.0, licencia **EUPL-1.2**. Se acompaña del documento *«Decisiones de diseño y descripción de la conversión de texto a código»*. Es **la fuente del seed**: no se transcribe el Anexo II a mano.

**Estructura verificada** (fichero `ENS_Anexo_II_rev_9`):

| OSCAL | ENS | Uso en BLENS |
|---|---|---|
| `groups` (class `family`) org / op / mp | Marco | `EnsMeasure.marco` |
| `groups` (class `subfamily`) op.pl, mp.if… | Familia | `EnsMeasure.familia` |
| `controls` sin class (73) | Medida | `EnsMeasure` |
| `controls` class `ens-refuerzo` (133), id `<medida>.rN` | Refuerzo | `EnsRefuerzo` |
| `parts` `requisitos` → `item` anidados (467 items), `props.label` = numeración literal | Requisitos atómicos | `EnsRequirementItem`: **ancla de checks y evidencias** |
| `parts` `overview` (17), `aclaracion` (1) | Texto introductorio | Ayuda contextual en UI |
| `props` ns `urn:es:ens`: `aplicacion-por`, `categoria`, `nivel`, `dimension` | Aplicabilidad | `ens_applicability` (motor puro) |
| `params` `tipo-param=seleccion-refuerzo`, `select.how-many=one` (4 medidas) | Disyunciones "R1 o R2…" | Elección obligatoria en la DdA |
| `metadata` (uuid v5, version, last-modified, license, link BOE) | Trazabilidad | `CatalogVersion` |

**Notas y huecos detectados:**
- **41 refuerzos sin props de aplicabilidad.** Ejemplos: org.2.r1, op.exp.1.r1–r4, mp.info.3.r5. Se interpretan como **opcionales**, pendiente de validar contra las tablas del RD (§17).
- **Errata confirmada contra el BOE:** en el JSON, **mp.eq.2** aparece titulada "Puesto de trabajo despejado" (igual que mp.eq.1); en el RD es **"Bloqueo de puesto de trabajo"**, aplicable por dimensión Autenticidad (n.a. en BAJO). El seed ya usa la aplicabilidad correcta. Reportar a la AEAD.
- **Discrepancia.** El documento cita `refuerzo-rol = obligatorio` (p. ej. mp.s.4.r1), pero esa prop **no aparece** en el JSON. El importador no debe depender de ella.
- **Sin enlaces cruzados** entre medidas en esta versión (según el propio documento).
- **Carácter informativo.** El valor jurídico es el del BOE. Se muestra el aviso del `metadata.remarks` en la UI.
- **No incluye:** checks CCN-STIC-808, evidencias esperadas, mapa MAGERIT, compensatorias ni banco de preguntas. Esa es **la capa propia de BLENS**, y se enlaza siempre al `id` OSCAL.

### 3.2 Componentes de seguridad y CPSTIC (op.pl.5)

- **Alcance.** op.pl.5 aplica a **MEDIA y ALTA**. Afecta a productos o servicios de terceros que forman parte de la **arquitectura de seguridad** o que las medidas citan expresamente. No afecta a todo el software.
- **Orden de decisión por componente:**
  1. **CPSTIC:** producto o servicio *cualificado*, en la versión concreta y aplicando su PES.
  2. **Certificado art. 19:** Common Criteria, LINCE o evaluación STIC con los RFS de CCN-STIC-140. Solo procede si no hay en CPSTIC nada con esa funcionalidad.
  3. **Compensatoria:** justificación en la DdA, riesgo asociado y plan de sustitución con fecha.
  4. **Fuera de alcance:** no es componente de seguridad. Hay que justificarlo.
- **Servicio de seguridad a terceros:** el producto debe estar cualificado en CPSTIC o aportar certificación equivalente.
- **Fuente de datos:** portal CPSTIC y guía **CCN-STIC-105**, con actualización **mensual**. Se modela como dato versionado (snapshot), igual que el catálogo ENS.
- **Taxonomía:** familias de producto de CCN-STIC-140.

#### 3.2.0 Uso de los datos del CPSTIC (criterio legal a validar)
- La licencia **CC BY-NC-ND 4.0** y el aviso legal protegen **el documento** (texto, maquetación). Los **datos fácticos** (producto, fabricante, versión, familia, categoría, fechas, código PES) no son obra protegible por derechos de autor.
- **Riesgos residuales:**
  - **Derecho *sui generis* sobre bases de datos** (LPI arts. 133 y ss.): ampara la extracción de una parte sustancial de una base con inversión sustancial. Está por confirmar si aplica a un catálogo de un organismo público.
  - El aviso legal **prohíbe expresamente el tratamiento informático**.
- **Criterio adoptado (minimización):**
  - Solo se extraen los campos necesarios para verificar un componente: nombre, fabricante, versión, familia, tipo, categoría ENS, revisión de validez, código PES, y edición + página. No se importan los productos aprobados (apartado 8), ni la clasificación, la fecha de inclusión, la descripción ni las observaciones.
  - Son **solo campos fácticos**. **No** se copian `Descripción` ni `Observaciones` (texto con posible autoría; del bloque de observaciones solo se guarda el código PES).
  - Siempre se cita la fuente: edición de la guía, página y enlace oficial.
  - El dataset no se redistribuye como tal (sin descarga ni API pública); solo se usa para verificar los componentes de cada cliente.
- **Pendiente:** validación con asesoría legal y **comunicación informativa al CCN** (coste bajo; conviene mantener buena relación, BLENS podría aspirar al apartado 9 del CPSTIC).

#### 3.2.1 Ingesta del CPSTIC (sin formato estructurado)
El CPSTIC **no se publica en formato estructurado** (a 09/2026). Proceso mensual semiautomático:
1. **Descarga.** Un admin de BLENS sube la nueva guía **CCN-STIC-105 (PDF)** al panel interno. Se guardan el PDF original y su `sha256` en S3.
2. **Extracción.** Tarea Celery con `pdfplumber` que deja las fichas en *staging* (`CpsticStagingRow`), con página de origen para trazabilidad. **Maquetación verificada (ed. 09/2026, 545 págs.):** la guía no son tablas sino **una ficha por producto**:
   - **Nombre:** en una celda de cabecera azul (RGB ≈ 0.18/0.455/0.71). Puede ocupar varias líneas.
   - **Etiquetas en Calibri-Bold 9** (el parser lee todas, pero solo persiste las de `CpsticEntry`): Versión, Fabricante, Familia, Tipo, Categoría ENS (cualificados) o Clasificación (aprobados), Fecha Inclusión, Revisión de Validez.
   - **Bloques de texto:** Descripción y Observaciones. En Observaciones suele venir el PES como `CCN-STIC nnnn`.
   - **Apartados:** 7 cualificados, 8 aprobados, 9 conformidad y gobernanza, con encabezados de sección en negrita y mayúsculas.
   - **Valores largos partidos:** quedan *por encima y por debajo* de la etiqueta y se reasignan por proximidad vertical.
   - **Prototipo:** 728 fichas (510 cualificados, 189 aprobados, 29 gobernanza), 0 errores de validación, 66 familias coherentes con su sección y ~2 min de proceso.
3. **Diff.** Comparación con el snapshot vigente: altas, bajas, cambios de versión o de categoría, y filas que no se han podido interpretar.
4. **Revisión humana.** El admin valida el diff en el panel. Nada se publica sin aprobación.
5. **Publicación.** Se crea un `CpsticSnapshot` nuevo y se lanza la revalidación de `SecurityComponent` (§10bis.2b).
- **Portal CPSTIC** (`cpstic.ccn.cni.es`, listado con filtros `familia`, `nivel_ens`, `nivel_clasificacion`, `tipo` y orden por fecha de alta): está **protegido con CAPTCHA antibots**. **Prohibido automatizar su acceso o sortear el CAPTCHA.**
- **Fuente alternativa aceptada:** un admin abre el listado en su navegador y guarda la página (HTML). BLENS la procesa igual que el PDF, por el mismo flujo de staging, diff y revisión. Suele ser más limpio que el PDF; antes de adoptarlo, confirmar que las condiciones de uso del portal lo permiten.
- Los filtros del portal definen los campos mínimos de `CpsticEntry`: familia, nivel ENS, nivel de clasificación y tipo.
- El parser vive en `engines/cpstic_parser` (puro, con pytest sobre PDFs de ejemplo). Si cambia la maquetación de la guía, los tests fallan y la publicación se bloquea.
- **Producto no encontrado.** Si un cliente declara un producto que no aparece, se abre una tarea de revisión interna, por si la extracción ha fallado, antes de mandarlo a la ruta art. 19 o compensatoria. Sirve para buscar alternativas cualificadas cuando el cliente usa un producto no incluido.

---

## 4. Alcance del producto — módulos

Cada módulo con responsabilidad y criterios de aceptación (DoD). Salvo el aislamiento de tenant (§14), todos entran en la v1.

### M1 · Categorización automática  *(gancho gratuito)*
- [ ] Cuestionario por dimensión (impacto: N/A, Bajo, Medio, Alto).
- [ ] Categoría = la más alta entre dimensiones; se **guarda el nivel de cada dimensión**. Muestra medidas y refuerzos aplicables calculados con `ens_applicability`, incluidos los de `nivel-dimension`.
- [ ] Export PDF. Uso **sin registro** (freemium).

### M2 · Declaración de Aplicabilidad (DdA)
- [ ] Genera `MeasureApplied` con `ens_applicability`. Obliga a resolver las **selecciones de refuerzo** (params OSCAL) y ofrece los refuerzos opcionales.
- [ ] Export de la DdA también en **OSCAL** (profile/SSP) además de PDF.
- [ ] No-aplicables con justificación obligatoria y compensatorias. Versionable, aprobable. Export PDF.

### M3 · Generación de documentación
- [ ] Cuestionario breve de organización → variables de plantilla.
- [ ] Plantillas alineadas con CCN-STIC-804; salida editable (HTML → PDF/DOCX). No plantillas genéricas.
- [ ] Los documentos entran en el control de versiones (M8).

### M4 · Checklist de cumplimiento
- [ ] Por medida: estado, madurez L0-L5, responsable, fecha, notas. Filtros por marco/familia/estado. "Qué te falta" para el umbral de tu categoría.

### M5 · Gestor de evidencias
- [ ] Subida de evidencias enlazadas a medida/check/requisito. Export del paquete completo (M9).
- [ ] **Grupos de opciones**: satisfacer una alternativa cierra el requisito y las demás quedan como "también válidas".
- [ ] Checklist de criterios de aceptación al subir y al revisar; rechazo con motivo concreto.
- [ ] Vigencia **por evidencia** (la cobertura del antivirus caduca en 3 meses, su política en 12) y panel de "caduca pronto".
- [ ] Una evidencia puede cubrir varios requisitos: se sube una vez y se enlaza a todos.

### M6 · Dashboard de cumplimiento
- [ ] Índices de cumplimiento y madurez por familia/marco/sistema; semáforo delta; heat-map; ranking de gaps. Export INES.
- [ ] **Indicador "listo para auditoría"**: media ponderada de madurez suficiente + evidencia viva + documentación vigente, con los tres componentes visibles. Definición en `docs/competencia_y_ux.md` §3. Nunca redondea al alza y no se presenta como conformidad.
- [ ] **Vistas cruzadas** riesgo↔activo↔medida: qué activos concentran riesgo y qué riesgos afectan a más activos.

### M7 · Motor de análisis de riesgos MAGERIT  *(diferenciador)*
- [ ] Activos, dependencias, amenazas, riesgo intrínseco/residual, tratamiento. Residual acoplado a la madurez. Informe exportable.

### M8 · Control de versiones documental
- [ ] Versionado inmutable con integridad demostrable (§11).

### M9 · Paquete de evidencias (formato CCN-STIC-808)
- [ ] Estructura de carpetas + índice navegable + matriz 808 + vista auditor (§10).

### M11 · Perfilado del sistema y carpeta de evidencias guiada  *(eje del producto — entra en v1)*
- [ ] Cuestionario de perfilado adaptativo (preguntas condicionadas por respuestas previas y por la categoría). Banco de preguntas = dato versionado en el catálogo.
- [ ] Las respuestas generan **hechos del sistema** (`ProfileFact`) y, vía reglas declarativas, **requisitos de evidencia** (`EvidenceRequirement`) por medida/check (§10bis).
- [ ] Cada requisito muestra: qué aportar, qué debe verse (p. ej. "la captura debe mostrar nombre de la política, alcance y fecha"), ejemplo, formato aceptado, vigencia y check 808 al que responde.
- [ ] **Opciones de evidencia, no imposiciones:** cada requisito se presenta como un grupo de alternativas válidas (export, captura, informe de tercero…) ordenadas por solidez ante el auditor. Con una basta. Catálogo en `docs/evidencias_por_herramienta.md`.
- [ ] **Pistas por producto:** identificado el producto (Defender, Entra ID, Veeam, Fortinet…), se indica la ruta concreta donde obtener la evidencia.
- [ ] **Rechazos típicos antes de subir** y criterios de aceptación marcables, que reutiliza el revisor para validar o rechazar con motivo concreto.
- [ ] Carpeta de evidencias **pre-estructurada** visible desde el primer día, con huecos pendientes y % de completitud por medida/familia/marco.
- [ ] Re-perfilado: cambiar una respuesta recalcula requisitos sin borrar evidencias (las sobrantes pasan a `FUERA_DE_ALCANCE`).
- [ ] **Preguntas autoexplicativas** (`docs/cuestionario_perfilado.md` §1bis): cada una con por qué se pregunta, dónde mirarlo (adaptado a las herramientas ya declaradas), opciones que describen situaciones reales y glosario en línea.
- [ ] **"No lo sé" no es una opción del menú**: es el botón "preguntárselo a otra persona", que exige elegir a quién y crea la tarea. Se mide la tasa por pregunta; por encima del 20 % la pregunta se reescribe.
- [ ] Cada requisito conserva la **trazabilidad**: pregunta/respuesta que lo originó → medida → check → evidencia.
- [ ] Genera la **Ficha previa para la entidad de certificación** (alcance, categoría, DdA, sedes, personas, proveedores, componentes). Ver `docs/cuestionario_perfilado.md` §7.

### M14 · Portal del auditor  *(v1 — cierra el círculo del producto)*
- [ ] Acceso por invitación con caducidad, **solo lectura**, sin cuenta de pago para el auditor.
- [ ] El auditor ve medidas, checks 808, evidencias con fecha y procedencia, y documentos vigentes.
- [ ] **Muestreo:** el auditor fija el tamaño de muestra, el sistema propone los elementos (altas/bajas, cambios, incidentes), él ajusta y queda registrado.
- [ ] **Peticiones de información** asignables a un responsable del cliente y cerradas con la evidencia aportada.
- [ ] Marcado de revisado por medida; los hallazgos caen al PAC (M13).
- [ ] Traza inmutable de todo lo que hace el auditor; enlaces S3 firmados y caducos.
- [ ] Detalle en `docs/competencia_y_ux.md` §4.

### M16 · Ingesta asistida por IA  *(POST-v1 — la v1 debe sostenerse sin esto)*
- [ ] El cliente arrastra lo que ya tiene (DdA o Excel previo, informe de auditoría anterior, políticas, carpeta de documentos, informe PILAR) y BLENS **propone**: madurez por medida, hallazgos al PAC, clasificación de documentos, emparejamiento con requisitos y huecos.
- [ ] **Detección de contradicciones** entre documentos, respuestas del perfilado y evidencias (la normativa dice 10 minutos de bloqueo, el MDM muestra 60). Señala las dos fuentes y propone cuál actualizar.
- [ ] Todo nace en estado `SUGERIDO`, con `origen = IA`, confianza y **cita de origen** (fichero, página, párrafo). Una persona acepta, corrige o rechaza, y queda en traza inmutable.
- [ ] **Nada sugerido cuenta** para el indicador de listo para auditoría hasta que se confirma.
- [ ] La IA **nunca** escribe en el catálogo ni entra en los motores: `risk_engine` y `scoring_engine` siguen siendo deterministas y solo consumen datos confirmados.
- [ ] Los documentos del cliente son **datos, no instrucciones**: extracción con esquema validado y casos de inyección en los tests.
- [ ] Desactivable por tenant. Diseño completo en `docs/ingesta_ia.md`.

### M15 · Portal de confianza público  *(POST-v1)*
- [ ] Página pública con el estado ENS del cliente (categoría, alcance, certificado, vigencia) para usar en licitaciones, con control de qué se publica.

### M12 · Difusión y acuse de normativa  *(v1 — genera evidencia por sí solo)*
- [ ] Publicar políticas y normas vigentes (M8) a los empleados y registrar su **acuse de lectura** con fecha, versión e identidad.
- [ ] Recordatorios a quien no ha acusado; informe de cobertura (% del personal, por versión).
- [ ] El propio registro **es la evidencia** de org.2 y mp.per.2: sustituye al PDF de firmas escaneadas.
- [ ] Igual para la **concienciación** (mp.per.3): convocatoria, asistencia y acuse gestionados en BLENS.

### M13 · Registro de incidentes y plan de acciones correctivas  *(v1 ligero)*
- [ ] Registro de incidentes: fecha, categoría, activo y medida afectados, impacto, resolución, notificación externa. Export en el formato del auditor.
- [ ] **PAC**: hallazgos (de auditoría, autoevaluación, análisis de riesgos, incidentes) con responsable, plazo y estado.
- [ ] Sin pretender ser un ITSM: si el cliente usa uno (B12.5), se importa o se enlaza.
- [ ] Cubre op.exp.7 y op.exp.9, y alimenta el ciclo de mejora (Anexo III).

### M10 · Multi-tenant / modo consultora  *(POST-v1 — depende del aislamiento de tenant, §14)*
- [ ] Gestión de cartera de clientes, plantillas reutilizables, marca blanca.

---

## 5. Stack y arquitectura (DECIDIDO)

Objetivo transversal: **BLENS debe ser él mismo ejemplar en seguridad** (aspira a ENS Alto).

**Stack definitivo:** **Django** (backend) + **Django Ninja** (API tipada) · **Vue 3 + Vite** (frontend) · **Aurora PostgreSQL** · **Celery + SQS** (async) · **AWS CDK en Python** (IaC).

- **Backend:** **Django** + **Django Ninja** (endpoints estilo FastAPI, esquemas Pydantic, **OpenAPI automático**). Python en todo el backend y los motores.
- **Frontend:** **Vue 3 + Vite** (con TypeScript ligero), **Pinia** (estado), **Vue Router**. UI con **Tailwind + shadcn-vue** reutilizando los tokens de marca BLENS (teal); PrimeVue es alternativa si pesa el data-grid. Tipos del cliente API **generados desde el OpenAPI** de Django Ninja (contrato tipado en ambos lados sin escribirlo a mano).
- **Trabajo pesado/async:** **Celery con broker SQS**. Generación de PDF/DOCX, ZIP de evidencias, recálculo masivo de riesgo → tareas Celery, **nunca en el ciclo request/response**. Chromium/WeasyPrint viven en el worker.
- **Base de datos:** **Amazon Aurora PostgreSQL** (multi-AZ). ORM de Django. Migraciones de Django versionadas.
- **Documentos:** **WeasyPrint** (HTML→PDF, desde las plantillas HTML de marca) + **python-docx** (Word editable).
- **IA (M16, post-v1):** **Amazon Bedrock en eu-west-1**, con retención cero y sin uso para entrenamiento. El proveedor del modelo es **subencargado**: entra en la lista de subprocesadores, el encargo de tratamiento y el RAT. La IA nunca toca los motores ni el catálogo.
- **Autenticación:** **Amazon Cognito** con MFA (DECIDIDO, §17/D1). **Cl@ve y la federación SAML de organismos quedan fuera**: quien usa BLENS es el personal de la organización, no la ciudadanía. Cl@ve aparece como respuesta del cliente en op.acc.5, nunca como forma de entrar al producto. 
- **Almacenamiento:** **S3 con versioning + Object Lock**; cifrado **SSE-KMS**.
- **IaC:** **AWS CDK en Python** (mismo lenguaje que el backend). Alternativa: Terraform (§17).
- **Despliegue:** frontend Vue como **estático en S3 + CloudFront**; backend Django + worker Celery en **ECS Fargate**. **No Vercel.**
- **Región / residencia del dato:** **AWS eu-west-1 (Irlanda)** (DECIDIDO, §17/D2). El requisito es que los datos estén **en la Unión Europea**, sin transferencias internacionales; así se cuenta al cliente. Riesgo asumido: un pliego que exija territorio español expresamente dejaría a BLENS fuera.
- **Determinismo numérico:** los motores usan **`Decimal`** (no `float`) con redondeo explícito; los resultados se almacenan en columnas `NUMERIC`. El análisis de riesgos acaba en un informe auditable: mismo input → mismo output, reproducible.
- **Testing:** **pytest** (backend y motores) + **Vitest/Playwright** (frontend/E2E).
- **Seguridad del producto:** WAF, GuardDuty, Security Hub, Config, Secrets Manager, entornos segregados.

---

## 5bis. Convenciones de UI/UX (derivadas de la competencia)

> **Precedencia:** en lo visual y de comportamiento (colores, tipografía, escalas, textos, estados, reglas de producto) manda **`design/README_handoff.md`**, que es alta fidelidad. En lo técnico (framework, estructura, estado, estilos, testing) manda este documento. Los prototipos `.dc.html` son referencia: **se recrean en Vue 3 con el sistema de estilos del proyecto, no se copian**. Los datos de los prototipos son de ejemplo y sus cálculos son aproximaciones: las fórmulas reales están en §8 y §9.

Requisitos que asumimos por los fallos documentados de las herramientas existentes (detalle y origen en `docs/competencia_y_ux.md` §5):

- **Divulgación progresiva real.** Por defecto simple; el modo experto añade opciones, nunca las muestra todas de golpe. El antipatrón es el modo "básico" que apenas cambia el menú.
- **Una sola voz.** Etiquetas consistentes, sin siglas sin explicar, glosario en línea. Nada de menús duplicados.
- **Editor de dependencias (M7):** multiselección de nodos, **% de dependencia visible en la arista**, zoom y desplazamiento fluidos, autoajuste y detección de ciclos con mensaje claro.
- **Valoraciones tipo hoja de cálculo:** navegación con teclado, tabulador entre celdas y pegado desde Excel. No doble clic + desplegable.
- **Ctrl+Z en toda la app** y guardado automático.
- **Colaborativo:** varios usuarios a la vez, con traza de quién cambió qué.
- **Declarado ≠ demostrado.** La UI distingue siempre la madurez declarada de la evidencia validada; el indicador de listo para auditoría no cuenta la madurez sin evidencia.
- **Avisos agrupados y accionables.** Sin ruido de notificaciones.
- **Accesibilidad WCAG AA** y uso con teclado, también en el grafo y las tablas.

---

## 6. Estructura del repositorio

```
blens/
  backend/
    config/               # proyecto Django: settings, celery app, urls raíz
    apps/
      catalog/            # catálogo ENS (medidas, refuerzos, checks) + comando seed
      tenancy/            # Tenant/Organizacion + tenant_id (aislamiento: fase posterior)
      compliance/         # System, categorización, DdA, MeasureAssessment
      documents/          # Documento + versión + generación (WeasyPrint/docx)
      profiling/          # cuestionario de perfilado, respuestas y hechos del sistema (M11)
      evidence/           # requisitos de evidencia, evidencias, revisión + paquete 808
      risk/               # activos, dependencias, amenazas, resultados de riesgo
    api/                  # Django Ninja: routers + schemas (Pydantic) → OpenAPI
    manage.py
  engines/                # PYTHON PURO, SIN Django ni I/O (importable por backend)
    risk_engine/          # propagación + cálculo MAGERIT (Decimal) + pytest
    scoring_engine/       # índices madurez/cumplimiento CCN-STIC-815 (Decimal) + pytest
    evidence_engine/      # hechos del perfil + DdA + reglas del catálogo → requisitos de evidencia + pytest
    ens_applicability/    # props OSCAL + categoría + niveles por dimensión → medidas/refuerzos aplicables + pytest
    cpstic_parser/        # guía CCN-STIC-105 (PDF) o listado del portal guardado (HTML) → filas normalizadas + pytest
    oscal_io/             # parseo del Catalog OSCAL (import) y export de DdA/resultados (sin Django)
  frontend/               # Vue 3 + Vite + TS (app)
  design/                 # handoff de diseño (alta fidelidad, 18 prototipos)
    README_handoff.md     #   tokens, especificación por pantalla y reglas visuales — MANDA en lo visual
    prototipos/           #   *.dc.html: referencia, NO código de producción (se recrean en Vue 3)
  landing/                # HTML estático de marketing (PENDIENTE: usar los tokens de design/README_handoff.md)
  infra/                  # AWS CDK en Python
  db/seed/
    oscal/                # JSON oficial AEAD tal cual (no editar) + LICENSE EUPL-1.2
    blens/                # capa propia (referencia ids OSCAL)
      magerit/            #   asset_types.yaml + threats.yaml (50) + measure_threat_map.yaml (269 pares) ✅
      checks/             #   checks derivados de los items OSCAL: generate_checks_from_oscal.py,
                          #     curate_checks.py y checks.<familia>.yaml — LAS 16 FAMILIAS (464 checks) ✅
      validate_seed.py    #   validador del seed completo — se ejecuta en CI
      questions.*.yaml + evidence_templates.*.yaml — LAS 16 FAMILIAS ✅
                          #     156 preguntas · 199 plantillas de evidencia · las 73 medidas cubiertas
                          #     (cifras reales que imprime validate_seed.py hoy)
  pyproject.toml          # gestor de deps (uv)
```

**Este árbol es el destino.** Tras F0 existen `backend/`, `frontend/`, `infra/`, `db/seed/`, `docs/` y `design/`; de `engines/` solo el prototipo del parser CPSTIC, y `landing/` no existe (§0).

**Contar items del catálogo:** el fichero tiene **467** partes `item`, pero solo **462 son requisitos**: las otras 5 cuelgan del `overview` de mp.eq.4 y son aclaraciones, así que `oscal_io` las aplana en el texto de la medida y no las importa como requisitos. Además solo hay **407 `props.label` distintos**: las etiquetas **no** son únicas entre medidas, y `validate_seed.py` imprime `items: 406` porque cuenta etiquetas, no items. Al anclar un `EnsCheck` a un `EnsRequirementItem`, la clave estable es el **id OSCAL** (`op.exp.6.req.2`), nunca el `label` a secas.

Los `engines/` son **paquetes Python puros y deterministas**, sin dependencias de Django ni de infraestructura, testeables en aislamiento. Solo `backend/apps/*` toca la base de datos vía el ORM.

---

## 7. Modelo de datos

Django ORM. **Toda entidad de tenant lleva `tenant_id`** (ver política en §14). El **catálogo** es global y versionado. Sketches de los modelos clave (amplía según haga falta):

### 7.1 Catálogo (global, versionado)
```python
class CatalogVersion(Model):        # 'ENS-2022-OSCAL-1.0.0 / MAGERIT-v3 / lib-2026.1'
    code; published_at; is_current
    oscal_uuid; oscal_version; source_version; source_last_modified
    license = 'EUPL-1.2'; source_sha256; source_s3_key   # JSON original inmutable
    blens_layer_version                                  # versión de la capa propia (checks, evidencias, mapas)

class EnsMeasure(Model):             # 73 medidas — importadas del OSCAL
    catalog = FK(CatalogVersion); code = 'op.exp.6'      # = id OSCAL (clave estable)
    marco = 'org'|'op'|'mp'; familia = 'op.exp'; nombre; requisitos_prose; overview
    aplicacion_por = 'CATEGORIA'|'NIVEL_DIMENSION'
    categorias: JSON; niveles: JSON; dimensiones: JSON   # tal cual las props urn:es:ens

class EnsRefuerzo(Model):            # 133 refuerzos
    measure = FK(EnsMeasure); code = 'op.exp.6.r1'; titulo; requisitos_prose
    aplicacion_por = nullable; categorias: JSON; niveles: JSON; dimensiones: JSON
    opcional: bool                   # True si no trae props de aplicabilidad (validar, §3.1)

class EnsSelectionParam(Model):      # disyunciones (op.acc.5/6, mp.com.4, mp.s.2)
    measure = FK(EnsMeasure); code = 'op.acc.5.prm.rfz.bajo'
    categoria = nullable; nivel = nullable; choices: JSON   # ids de refuerzos; se elige uno

class EnsRequirementItem(Model):     # items OSCAL: requisito atómico con numeración literal
    catalog; code = 'op.exp.6.req.2'; label = 'op.exp.6.2'
    measure = FK(EnsMeasure); refuerzo = FK(EnsRefuerzo, null=True)
    parent = FK('self', null=True); prose; orden

class EnsCheck(Model):               # CAPA PROPIA: verificación, anclada al item OSCAL
    measure = FK(EnsMeasure); refuerzo = FK(EnsRefuerzo, null=True)
    item = FK(EnsRequirementItem)    # 1 check = 1 requisito atómico de la norma
    code = 'CHK-op.exp.6.2'; descripcion
    metodo: JSON                     # ['DOCUMENTAL','INSPECCION_TECNICA','ENTREVISTA','MUESTREO']
    evidencia_esperada = M2M(EvidenceTemplate)

# La aplicabilidad NO se guarda en tabla: se deriva con engines/ens_applicability
# (categoría + niveles por dimensión + props OSCAL → medidas y refuerzos aplicables,
#  refuerzos opcionales y selecciones pendientes).

class MaturityEffectiveness(Model):  # L0-L5 → eficacia (CCN-STIC-815) — CONFIGURABLE
    level: int (PK 0..5); label; effectiveness: Decimal  # 0/.1/.5/.8/.9/1.0

# --- MAGERIT ---
class MageritAssetType(Model): catalog; code; name; is_terminal
class MageritThreat(Model):    catalog; code; name; category
class MageritThreatDefault(Model):
    threat = FK(MageritThreat); dim; default_degradation: Decimal; default_frequency: Decimal

class MeasureThreatMap(Model):       # biblioteca curada (equivalente a la lib de PILAR)
    catalog; measure = FK(EnsMeasure); threat = FK(MageritThreat)
    dim = nullable          # NULL = todas las dimensiones
    aspect = 'FREQ'|'IMPACT'; weight: Decimal  # 0..1, reducción máx al 100% de eficacia

# --- CPSTIC (op.pl.5) — snapshot mensual ---
class CpsticSnapshot(Model):
    code = '2026-09'; published_at; source_url; source_sha256; is_current
class CpsticFamily(Model):           # taxonomía CCN-STIC-140
    snapshot = FK(CpsticSnapshot); code; nombre; rfs_ref
class CpsticEntry(Model):           # SOLO los campos necesarios para verificar (minimización, §3.2.0)
    snapshot = FK(CpsticSnapshot); family = FK(CpsticFamily)   # familia: casar funcionalidad y sugerir alternativas
    apartado = 'CUALIFICADO'|'CONFORMIDAD_GOBERNANZA'           # los APROBADOS (clasificada) no se importan
    nombre; fabricante                                          # casar con lo que declara el cliente
    version                                                     # la cualificación es por versión
    tipo = 'PRODUCTO'|'SERVICIO'                                # un servicio implica además op.ext/op.nub
    categoria_ens = 'BASICA'|'MEDIA'|'ALTA'|'NA'                # ¿vale para la categoría del sistema?
    revision_validez: date                                      # caducidad
    pes_codigo = nullable            # 'CCN-STIC-1217' o 'PENDIENTE'; la evidencia de configuración se pide contra él
    source_page: int                 # trazabilidad: edición (snapshot) + página
class CpsticStagingRow(Model):       # extracción pendiente de revisión
    upload_sha256; raw: JSON; parsed: JSON; source_page; estado = 'OK'|'DUDOSA'|'ERROR'; cambio = 'ALTA'|'BAJA'|'MODIFICADA'|'SIN_CAMBIO'
    medidas_relacionadas: JSON       # ids OSCAL, curado por BLENS

# --- Perfilado y evidencias (M11) ---
class ProfileQuestion(Model):        # banco de preguntas
    catalog; code = 'infra.cpd.tipo'; bloque; texto
    por_que; como_saberlo; ejemplos: JSON; a_quien_preguntar; glosario: JSON  # ver docs §1bis
    tipo = 'SINGLE'|'MULTI'|'BOOL'|'TEXT'|'NUMBER'|'DATE'|'TOOL'|'VENDOR'|'LIST'
    show_if: JSON          # condición (JSON Logic) sobre hechos previos y categoría
    orden; minutos_estimados
class ProfileOption(Model):
    question = FK(ProfileQuestion); code = 'propio'; label
    emits: JSON            # hechos que produce: {"cpd": "propio"}

class EvidenceTemplate(Model):       # requisito de evidencia "tipo" — lo que pediría un auditor
    catalog; code = 'EV-mp.if.1-02'
    option_group = nullable          # varias plantillas alternativas cubren el mismo requisito: basta UNA
    preferencia: int                 # orden dentro del grupo (1 = la más sólida para el auditor)
    criterios_aceptacion: JSON       # ["se ve la fecha", "se ve el total de equipos"] — checklist de subida y de revisión
    rechazos_tipicos: JSON           # avisos preventivos antes de subir
    measure = FK(EnsMeasure); check = FK(EnsCheck, null=True)
    item = FK(EnsRequirementItem, null=True); refuerzo = FK(EnsRefuerzo, null=True)
    applies_if: JSON       # condición (JSON Logic) sobre hechos + categoría + refuerzos
    refuerzo_min = nullable
    titulo; instrucciones   # qué aportar y QUÉ DEBE VERSE
    tipo = 'DOCUMENTO'|'CAPTURA'|'EMAIL'|'REGISTRO'|'CONTRATO'|'CERTIFICADO'|'FOTO'|'EXPORT_CONFIG'|'ACTA'
    formatos: JSON; ejemplo_url; obligatoria: bool
    vigencia_dias = nullable   # p. ej. 365 para concienciación anual
    carpeta_paquete        # ruta destino en §10
    generable: bool        # True si BLENS la produce (M3) en lugar de pedirla

class ProductEvidenceHint(Model):    # dónde encontrar la evidencia en cada producto conocido
    catalog; template = FK(EvidenceTemplate)
    producto_match: JSON             # fabricante/producto (casa con SecurityComponent y CpsticEntry)
    instrucciones                    # "Portal Defender → Activos → Inventario de dispositivos → Exportar"
```

### 7.2 Datos del tenant
```python
class Tenant(Model): nombre; ...                 # organización cliente

# --- Roles y permisos (docs/roles_y_permisos.md) ---
class Membership(Model):                         # el rol vive aquí, no en el usuario
    tenant = FK(Tenant); user = FK(User)
    role = 'PROPIETARIO'|'RSEG'|'TECNICO'|'COLABORADOR'|'DIRECCION'|'AUDITOR'|'CONSULTOR'
    systems = M2M(System, blank=True)            # vacío = todos los del tenant
    bloques: JSON                                # solo COLABORADOR
    expires_at = nullable                        # AUDITOR y CONSULTOR caducan
    estado = 'ACTIVA'|'PENDIENTE'|'CADUCADA'|'REVOCADA'   # unique(tenant, user)
class Invitation(Model):
    tenant = FK(Tenant); email; role; systems: JSON; bloques: JSON
    token_hash; expires_at; used_at = nullable; created_by = FK(User)
class AuditLog(Model):                           # append-only con hash encadenado (op.exp.8/9)
    tenant = FK(null=True); user = FK(null=True); accion; objeto_tipo; objeto_id
    datos: JSON; ip; created_at; prev_hash; hash
class System(Model):                             # sistema de información bajo alcance
    tenant = FK(Tenant, null=True)               # v1: nullable, sin filtrar (§14)
    nombre; categoria = 'BASICA'|'MEDIA'|'ALTA'
class DimensionValuation(Model):                 # categorización (M1)
    system = FK(System); dim; nivel = 'NA'|'BAJO'|'MEDIO'|'ALTO'   # unique(system, dim); lo usa ens_applicability

class DeclaracionAplicabilidad(Model):           # DdA (M2)
    tenant = FK(Tenant, null=True); system = FK(System)
    version: int; estado; aprobador; fecha
class MeasureApplied(Model):
    dda = FK(DeclaracionAplicabilidad); measure = FK(EnsMeasure)
    aplica: bool; justificacion; refuerzos: JSON; compensatoria
    selecciones: JSON      # {param_id: refuerzo elegido} — obligatorio si hay EnsSelectionParam

class MeasureAssessment(Model):   # FUENTE ÚNICA de madurez: alimenta scoring Y riesgo
    tenant = FK(Tenant, null=True); system = FK(System); measure = FK(EnsMeasure)
    maturity_level: int; objetivo: int; applies: bool
    responsable; fecha_limite; notas             # unique(system, measure)

# --- Riesgo (M7) ---
class Asset(Model): tenant=FK(null=True); system=FK; asset_type=FK; name
class AssetValuation(Model): asset=FK; dim; own_value: Decimal   # 0..10
class AssetDependency(Model):
    parent = FK(Asset, related='depende_de'); child = FK(Asset, related='soporta')
    degree: Decimal  # 0..1   (grafo DAG, sin ciclos)
class ThreatInstance(Model):
    tenant=FK(null=True); asset=FK; threat=FK(MageritThreat); dim
    frequency: Decimal; degradation: Decimal      # unique(asset, threat, dim)
class RiskResult(Model):
    tenant=FK(null=True); threat_instance=FK
    accumulated_value: Decimal; intrinsic_risk: Decimal
    residual_freq_factor: Decimal; residual_impact_factor: Decimal
    residual_risk: Decimal; computed_at
class RiskTreatment(Model):
    tenant=FK(null=True); threat_instance=FK
    decision = 'MITIGAR'|'ACEPTAR'|'TRANSFERIR'|'EVITAR'; target_risk: Decimal; owner; due_date; notes

# --- Documentos y evidencias (M3/M5/M8) ---
class Documento(Model): tenant=FK(null=True); system=FK; tipo; titulo
class DocumentoVersion(Model):
    documento=FK; s3_version_id; sha256; autor
    estado = 'BORRADOR'|'EN_REVISION'|'APROBADO'|'VIGENTE'|'OBSOLETO'; firma; fecha
class Evidencia(Model):
    tenant=FK(null=True); measure=FK(null=True); check=FK(null=True)
    requirement = FK(EvidenceRequirement, null=True)
    documento_version=FK; tipo; fecha_evidencia     # fecha del hecho, no de subida
    estado = 'APORTADA'|'EN_REVISION'|'VALIDADA'|'RECHAZADA'|'CADUCADA'
    revisor; motivo_rechazo

# --- Componentes de seguridad (op.pl.5) ---
class SecurityComponent(Model):                   # vive sobre el inventario único (Asset)
    tenant=FK(null=True); system=FK; asset = FK(Asset)
    fabricante; producto; version_instalada; funcion   # EDR, firewall, MFA, VPN…
    medidas: JSON                                 # ids OSCAL a los que da soporte
    ruta = 'CPSTIC'|'CERTIFICADO_ART19'|'COMPENSATORIA'|'FUERA_DE_ALCANCE'|'PENDIENTE'
    cpstic_entry = FK(CpsticEntry, null=True)     # match confirmado por el usuario (producto + versión)
    certificacion_ref; pes_aplicado: bool
    justificacion; riesgo = FK(ThreatInstance, null=True); plan_sustitucion_fecha
    ultima_verificacion_snapshot = FK(CpsticSnapshot, null=True)

# --- Perfilado (M11) ---
class ProfileAnswer(Model):
    tenant=FK(null=True); system=FK; question=FK(ProfileQuestion)
    value: JSON; respondido_por; fecha            # unique(system, question); historial conservado
class ProfileFact(Model):                         # derivado de respuestas; entrada del evidence_engine
    tenant=FK(null=True); system=FK; key; value: JSON; source_answer=FK(ProfileAnswer)
class EvidenceRequirement(Model):                 # instancia de EvidenceTemplate para ESTE sistema
    tenant=FK(null=True); system=FK; template=FK(EvidenceTemplate)
    estado = 'PENDIENTE'|'APORTADA'|'VALIDADA'|'CADUCADA'|'FUERA_DE_ALCANCE'|'NO_APLICA_JUSTIFICADO'
    origen: JSON           # hechos/respuestas que lo dispararon (trazabilidad para el auditor)
    responsable; fecha_limite; proxima_renovacion  # unique(system, template)
```

---

## 8. Motor de scoring (madurez / cumplimiento)

`engines/scoring_engine` (puro, determinista, `Decimal`, pytest). Fuente: `MeasureAssessment`.
- **Por medida:** L0-L5 → % (0/10/50/80/90/100); objetivo por categoría; **delta** = medido − objetivo.
- **Semáforo:** verde si delta > −1, amarillo entre −1 y −2, rojo si ≤ −2.
- **Composición por familia/marco:** el **peor componente** (no la media).
- **Índices:** cumplimiento y madurez por familia/marco/sistema.
- **Export INES:** estado en el formato del cuestionario (CCN-STIC-824/844).

---

## 9. Motor de análisis de riesgos MAGERIT

`engines/risk_engine` (puro, `Decimal`, con **test de regresión** del ejemplo §9.3). **Sin PILAR.**

### 9.1 Propagación de valor (grafo de dependencias)
DAG (detectar y rechazar ciclos). El valor nace en activos terminales y desciende a los que los soportan:
```
accumulated_value(a,d) = max( own_value(a,d),
    max sobre { p : arista p→a } de  degree(p→a) × accumulated_value(p,d) )
```
Orden topológico (cada activo tras los que dependen de él). Cachear e invalidar al editar grafo/valoraciones.

### 9.2 Riesgo intrínseco → residual (acoplamiento con la madurez)
Para cada `ThreatInstance` (activo a, amenaza t, dimensión d):
```
V   = accumulated_value(a,d)
R0  = V × degradation(t,d) × frequency(t,d)                 # intrínseco

e(m) = MaturityEffectiveness[ MeasureAssessment(m).maturity_level ]   # 0..1, desde la madurez
w(m) = MeasureThreatMap(m,t,d,aspect).weight

factor_freq   = Π sobre m∈FREQ   de (1 − e(m)·w(m))
factor_impact = Π sobre m∈IMPACT de (1 − e(m)·w(m))

R_residual = V × degradation(t,d) × factor_impact × frequency(t,d) × factor_freq
```
Combinación multiplicativa (defensa en profundidad) por defecto; alternativa `1 − max(e·w)` parametrizable. Todo en `Decimal` con redondeo explícito.

### 9.3 Ejemplo trabajado (test de regresión obligatorio)
Servidor (hereda D=9 de la Sede vía dependencia 100%), amenaza DoS: freq=2, degr=0.80 → **R0 = 14.4**.
Salvaguardas: op.mon.1 (FREQ, w=0.4, L3→e=0.8); mp.com.* (FREQ, w=0.5, L2→e=0.5); op.cont.* (IMPACT, w=0.6, L3→e=0.8).
`factor_freq = (1−0.32)(1−0.25) = 0.510`; `factor_impact = 0.520` → **R_residual ≈ 3.82** (−73%). Test con tolerancia ±0.01.

### 9.4 Agregación y simulación
Por activo `max` (peor caso) o `Σ` (exposición), configurable. Simulador inverso: dado `target_risk`, qué madurez mínima de qué medidas lo alcanza.

---

## 10. Motor de evidencias y paquete de auditoría

`backend/apps/evidence` + tareas Celery. **No hay formato legal único**; estructura **plantilla-driven y configurable por perfil de auditor**, derivada de CCN-STIC-808 y del Anexo II.
```
00_Gobernanza/  01_Alcance_y_Categorizacion/  02_Analisis_de_Riesgos/
03_Declaracion_de_Aplicabilidad/  04_[org]/  05_[op]/  06_[mp]/
07_Auditoria_y_Mejora/  99_Indice/
```
**Salidas:** ZIP estructurado · índice navegable HTML (medida→check→documento→evidencia) · PDF maestro (WeasyPrint) · matriz de evidencias Excel/CSV estilo 808 · **vista auditor** de solo lectura (presigned S3 con caducidad).

---

## 10bis. Perfilado del sistema y requisitos de evidencia (eje del producto)

**Idea:** el cliente no sabe qué pide un auditor. BLENS sí. Las preguntas describen el sistema; las reglas del catálogo traducen esa descripción en **la lista exacta de evidencias que pediría un auditor ENAC**, cada una con instrucciones concretas. El cliente rellena huecos; BLENS maqueta.

### 10bis.1 Flujo
```
Categoría (M1) + DdA (M2)
        │
Cuestionario de perfilado (M11) ──► ProfileAnswer ──► ProfileFact
        │                                                   │
        └──────────────► evidence_engine (puro) ◄───────────┘
                               │  EvidenceTemplate.applies_if
                               ▼
                    EvidenceRequirement (carpeta a medida)
                               │  el cliente aporta / BLENS genera (M3)
                               ▼
               Evidencia ─► revisión ─► VALIDADA ─► Paquete 808 (M9)
```

### 10bis.2 Ejemplos de reglas (orientativo; el contenido real vive en `db/seed`)
| Respuesta del cliente | Medidas | Evidencias que se solicitan |
|---|---|---|
| "Tenemos **CPD propio**" | mp.if.1–mp.if.7 | Plano/croquis de la sala; fotos del control de acceso; registro de entradas/salidas (personas y equipamiento); contratos y partes de mantenimiento de climatización, SAI y extinción; informe de última prueba del SAI/grupo |
| "El CPD es de un **proveedor / nube**" | op.ext.1, op.ext.2, op.nub.1 | Contrato y SLA; certificado de conformidad ENS del proveedor (categoría ≥ la propia); informes periódicos del servicio; cláusulas de seguridad y encargo de tratamiento |
| "Usamos **[herramienta EDR/antivirus]**" | op.exp.6 | Captura de consola con cobertura de equipos; captura de política aplicada; captura con fecha de última actualización de firmas; export de incidencias del último trimestre |
| "Hacemos **acciones de concienciación**" | mp.per.3 (+ mp.per.4 si formación) | Email de convocatoria; material impartido; lista de asistencia/registro en plataforma; evaluación o certificado. **Vigencia anual** |
| "Tenemos **copias de seguridad**" | mp.info.6, op.cont.3 | Captura/export de la política de copias; registro de ejecuciones; **acta de prueba de restauración** fechada |
| "Usamos **MFA**" | op.acc.6 | Captura de la configuración obligatoria de MFA; export de usuarios con MFA activo; política de autenticación (generable por M3) |

### 10bis.2b Herramientas y hardware de seguridad
Cuando el perfilado detecta un componente de seguridad (p. ej. "usamos X como EDR"):
1. BLENS busca en el snapshot CPSTIC vigente (fuzzy por fabricante y producto) y **el usuario confirma producto y versión**. La cualificación va ligada a la versión.
1b. Se instancian las **evidencias funcionales de su familia** (antivirus/EDR, cortafuegos, SIEM, identidad, copias…) con sus opciones alternativas y sus pistas para ese producto: `docs/evidencias_por_herramienta.md` §3.
2. Se asigna la ruta (§3.2) y se instancian las evidencias de esa ruta:
   - **CPSTIC:** ficha CPSTIC fechada, captura de la versión instalada y evidencia de configuración según el PES.
   - **Certificado art. 19:** certificado CC/LINCE, alcance y cobertura de RFS, y evidencia de que ninguna alternativa CPSTIC cubre la funcionalidad (consulta fechada al snapshot).
   - **Compensatoria:** justificación, referencia al riesgo en M7, medidas compensatorias y plan de sustitución con fecha. Se sugieren las alternativas cualificadas de la misma familia.
3. **Caducidad:** la ficha trae `Revisión de Validez`. BLENS avisa con antelación (p. ej. 90 días) y marca como no válido un componente cuya cualificación ha vencido. **La propia guía puede listar fichas ya vencidas** (en la ed. 09/2026 hay 4): no se asume validez por aparecer en ella.
4. **PES:** si la ficha indica "pendiente de publicación" o "en proceso de actualización", la evidencia de configuración segura se pide sobre la guía de bastionado del fabricante y queda anotado.
5. **Riesgo residual del producto:** la guía advierte que la cualificación no avala al fabricante (por ejemplo, envío de datos a sus servidores) y que el RSEG debe valorar y mitigar esos riesgos. Por eso cada `SecurityComponent` en ruta CPSTIC genera también una amenaza a valorar en M7.
6. **Revalidación mensual** (tarea Celery programada): al publicarse un snapshot nuevo, se recalcula cada componente. Se avisa si una versión deja de estar cualificada, si el producto sale del catálogo o si aparece una alternativa cualificada para un componente en ruta compensatoria.
7. En categoría BÁSICA, op.pl.5 no es obligatoria: se muestra como recomendación y no bloquea.
8. Los **productos aprobados** (apartado 8) son para información clasificada: se muestran solo como referencia, porque la ruta ENS usa los cualificados (apartado 7) y los de conformidad y gobernanza (apartado 9).

### 10bis.3 Reglas de diseño
- **Las reglas son dato**: condiciones declarativas (JSON Logic) en `EvidenceTemplate.applies_if` y `ProfileQuestion.show_if`. Nada hardcodeado.
- **`evidence_engine` puro y determinista**: `(hechos, categoría, DdA, catálogo) → requisitos`. Mismo input → misma carpeta. pytest con casos por perfil tipo (PYME con nube, ayuntamiento con CPD propio…).
- **Instrucciones accionables**: cada requisito dice *qué debe verse* en la evidencia, no solo su nombre. Incluye ejemplo anonimizado.
- **Evidencia generable vs aportable**: si BLENS puede producirla (políticas, normativa, DdA, análisis de riesgos, actas plantilla), se enlaza con M3 en vez de pedirla.
- **Fecha del hecho y vigencia**: la evidencia guarda la fecha del hecho; si caduca (`vigencia_dias`), el requisito vuelve a `PENDIENTE` y avisa antes.
- **Madurez soportada**: un `MeasureAssessment` con nivel ≥ L2 sin evidencias obligatorias validadas se marca **"madurez no soportada"** en dashboard y checklist. Es lo primero que detecta un auditor.
- **No aplica ≠ pendiente**: el cliente puede marcar un requisito como no aplicable con justificación; queda visible en el paquete.
- **Re-perfilado seguro**: recalcular nunca borra evidencias; lo que deja de aplicar pasa a `FUERA_DE_ALCANCE`.
- **Revisión**: estados `APORTADA → EN_REVISION → VALIDADA/RECHAZADA` con motivo. Validación automática básica (formato, tamaño, fecha, no vacío); la revisión de contenido la hace una persona (RSEG o consultor).

### 10bis.4 Salida para el auditor
Cada evidencia se coloca en su carpeta (§10) con nombre normalizado:
`05_[op]/op.exp.6/EV-op.exp.6-03_captura-consola-EDR_2026-09-10.png`
El índice (HTML y PDF) muestra por check: evidencias validadas, fecha, vigencia, **pregunta que originó el requisito** y huecos justificados. El auditor audita, no persigue documentación.

---

## 11. Control de versiones documental

- **Inmutabilidad:** S3 versioning + Object Lock; cada `DocumentoVersion` guarda `sha256`, autor, fecha, estado.
- **Workflow:** `BORRADOR → EN_REVISION → APROBADO → VIGENTE → OBSOLETO`; aprobador (RSEG/Comité); opcional firma + sello de tiempo (TSA).
- **Snapshot por auditoría:** congelar la versión vigente en instantánea fechada. **Diff e historial** por documento.

---

## 12. Flujos de usuario

El "camino en 3 pasos" de la landing, mapeado a módulos:
1. **Categoriza** → M1 (gratis, sin registro) → medidas aplicables + DdA (M2).
2. **Cuéntanos tu sistema** → M11 perfilado → carpeta de documentación y evidencias a medida.
3. **Genera documentación** → M3 (rellena los huecos generables) → versionado (M8).
4. **Completa evidencias y seguimiento** → M5 (huecos guiados) + M4 + M6 + M7.
5. **Auditoría** → M9: paquete maquetado y trazado, listo para el auditor.

---

## 13. Requisitos no funcionales

- **Seguridad:** BLENS aspira a ENS Alto; MFA, cifrado en tránsito y reposo, secretos gestionados, mínimos privilegios, registro append-only con hash encadenado (op.exp.8/9).
- **Auditabilidad:** toda acción relevante deja traza inmutable.
- **Privacidad:** RGPD; borrado y portabilidad por tenant. Lista de subprocesadores mínima y en la UE (cada SaaS de terceros es un subencargado ante el comprador público).
- **i18n:** español por defecto. Preparado para multi-idioma, sin prioridad.
- **Accesibilidad:** WCAG AA en app y landing; foco visible, `prefers-reduced-motion`.
- **Rendimiento:** recálculo de scoring/riesgo incremental y cacheado; trabajo pesado en Celery.

---

## 14. Alcance de la v1 y gate previo a producción

### 14.1 Alcance v1
La v1 es **el producto completo (M1–M9 + M11–M14)**. BLENS se construye como **producto SaaS para vender** (DECIDIDO, §17/D0), lo que implica registro, planes y cobro en la v1, y el gate de aislamiento de tenant **antes del primer cliente real**, sin excepciones. Queda **fuera de la v1** el **aislamiento de tenant** y, por depender de él, el **modo consultora multi-cliente (M10)**.

### 14.2 tenant_id: andamiaje SÍ, aislamiento NO (en v1)
- **En la v1 se incluye `tenant_id`** (FK a `Tenant`, **nullable, SIN filtrado**) en todos los modelos de tenant, desde la primera migración.
- ⚠️ **La columna existe pero NO aísla nada.** Es andamiaje para que el aislamiento futuro sea aditivo (no una migración de datos). No da ninguna garantía de seguridad y no debe tratarse como tal.
- En v1 **no** se construyen todavía los managers scoped ni la RLS: se prioriza simplicidad.

### 14.3 GATE previo a producción (BLOQUEOS de release)
**BLENS no se expone a clientes reales hasta que TODO esto esté verde.** No es deuda difusa: es una puerta.
- [ ] `tenant_id` **NOT NULL** en todos los modelos de tenant.
- [ ] **Manager por defecto tenant-scoped**: `.objects` filtra por el tenant del contexto (contextvar fijado por middleware desde el usuario autenticado). Acceso sin filtrar solo vía `unscoped` explícito y revisable.
- [ ] El `tenant_id` sale **siempre del contexto autenticado**, jamás de un input del request.
- [ ] **RLS de PostgreSQL** activada (`FORCE ROW LEVEL SECURITY`; rol de app no superusuario; `SET LOCAL app.tenant_id` **dentro de transacción** — con pooling en modo transacción, solo `SET LOCAL` es seguro).
- [ ] **Tests negativos en CI**: un usuario del tenant A intentando leer/escribir datos del tenant B **debe fallar**. Esta suite se queda para siempre.
- [ ] Revisión de que no hay queries que salten los managers scoped.

---

## 15. Convenciones para Claude Code

**Stack fijado (§5). No reabrir** sin motivo: Django + Django Ninja · Vue 3 + Vite · Aurora PostgreSQL · Celery + SQS · WeasyPrint/docx · AWS CDK (Python) · Cognito (sin Cl@ve ni SAML) · pytest/Vitest · región eu-west-1. **Antes de asumir, pregunta** en cualquier otra decisión con coste de reversión alto.

**Reglas de trabajo:**
- **Motores puros primero.** `risk_engine` y `scoring_engine` como paquetes Python deterministas **con pytest**, antes de cablear nada. El ejemplo §9.3 es test de regresión obligatorio.
- **`Decimal`, no `float`,** en todos los cálculos de riesgo y scoring; redondeo explícito; almacenar en `NUMERIC`.
- **El catálogo es dato, no código.** Las 73 medidas y 133 refuerzos se **importan del OSCAL oficial** (`db/seed/oscal`, sin editar). Checks, `measure_threat_map`, preguntas y plantillas van en `db/seed/blens` referenciando ids OSCAL. Todo versionado por `CatalogVersion`. No hardcodear medidas en la lógica.
- **Los checks se derivan de los items OSCAL, no se inventan.** `generate_checks_from_oscal.py` produce el esqueleto (1 check por requisito atómico); la curación añade método de verificación y evidencias. Garantiza cobertura total y trazabilidad al texto de la norma. Pendiente contrastar con la CCN-STIC-808.
- **Validación del seed MAGERIT en CI:** toda medida referenciada existe en el catálogo OSCAL; pesos en (0, 0.7]; toda amenaza tiene al menos una salvaguarda; **las 73 medidas aparecen al menos una vez** en el mapa; sin pares duplicados.
- **`db/seed/blens/validate_seed.py` es la validación del seed en CI.** Comprueba referencias, hechos huérfanos, preferencias duplicadas, checks sin item válido y cobertura MAGERIT. Falla el build ante cualquier error.
- **El seed no está validado externamente.** Rechazos típicos, vigencias y métodos de verificación son criterio propio hasta que un auditor ENAC los contraste (`docs/validacion_externa.md`). Al validarlos, anotar `validado_por` y `validado_en` en el fichero.
- **Validación del seed propio en CI:** todo `measure`/`refuerzo` referenciado debe existir en el catálogo OSCAL; todo hecho usado en `show_if`/`applies_if` debe emitirlo alguna opción; cada medida aplicable debe tener al menos una plantilla de evidencia alcanzable. Si falla, el build falla.
- **Importador OSCAL idempotente y validado.** Valida contra el esquema OSCAL 1.1.3, guarda hash y JSON original y compara con la versión anterior. Si una actualización elimina o renombra un id referenciado por la capa propia, **el import falla** con un informe; no deja referencias huérfanas.
- **Las evidencias se piden por reglas, no por listas fijas.** Banco de preguntas y `EvidenceTemplate` en `db/seed`; la lógica en `engines/evidence_engine`.
- **Una sola fuente de verdad para la madurez** (`MeasureAssessment`): la consumen scoring y riesgo. No duplicar.
- **`tenant_id` en todo modelo de tenant desde la 1ª migración** (nullable en v1). Ver §14 — es andamiaje, no seguridad.
- **Aislamiento de tenant = gate de producción (§14.3),** no v1. Pero escribe el acceso a datos de forma que enchufarlo después sea aditivo (un único punto de acceso por app; nada de queries ad-hoc dispersas).
- **Trabajo pesado a Celery.** PDF/DOCX, ZIP de evidencias, render y recálculo masivo → tareas Celery. Nunca en el ciclo request/response.
- **API tipada:** define los schemas Pydantic en Django Ninja; **genera los tipos TS del frontend desde el OpenAPI**, no los escribas a mano.
- **Migraciones de Django** versionadas; nunca editar una aplicada, añadir una nueva.
- **Un único punto de decisión de permisos:** `can(user, accion, objeto)` resuelve rol, ámbito de sistema, bloques y separación de funciones. Nada de comprobaciones dispersas en las vistas; ahí se enchufa después el aislamiento de tenant (§14.3).
- **Separación de funciones impuesta por el sistema:** quien aporta una evidencia no la valida, y quien redacta un documento no lo aprueba, aunque tenga el rol. Si la organización es demasiado pequeña, se registra la excepción justificada. Ver `docs/roles_y_permisos.md` §3.
- **Sin secretos en el repo.** Secrets Manager / variables de entorno.
- **DoD por módulo:** criterios de §4 marcados + tests + migración + endpoint Django Ninja tipado.
- **Comandos.** Los marcados con ⛔ son el contrato de fases posteriores: todavía no existen.
  ```
  # Backend (Python, gestor: uv)
  uv sync                                 # instalar deps
  docker compose up -d                    # Postgres 5434 · Redis 6381
  uv run backend/manage.py migrate        # migraciones
  uv run backend/manage.py runserver 8001 # dev API (/api/health, /api/docs)
  uv run pytest                           # tests (motores al 100%)
  uv run ruff check . && uv run black --check .
  cd backend && uv run celery -A config worker -l info   # worker async

  # Seed: validación contra el catálogo OSCAL (se ejecuta en CI)
  uv run python db/seed/blens/validate_seed.py db/seed/oscal/ENS_Anexo_II_rev_9.json
  # Esqueleto de checks de una familia (se CURA a mano después)
  uv run python db/seed/blens/checks/generate_checks_from_oscal.py \
      db/seed/oscal/ENS_Anexo_II_rev_9.json op.exp

  uv run backend/manage.py import_ens_oscal db/seed/oscal/ENS_Anexo_II_rev_9.json
  # idempotente; falla si una versión nueva deja huérfana una referencia de la capa propia
  ⛔ uv run backend/manage.py seed_blens     # checks, measure_threat_map, preguntas, plantillas

  # Frontend (Vue)
  pnpm --dir frontend install
  pnpm --dir frontend dev                 # http://localhost:5175
  pnpm --dir frontend test                # vitest
  pnpm --dir frontend build               # vue-tsc + build
  pnpm --dir frontend gen:api             # OpenAPI (Django Ninja) → tipos TS

  # Infra (deps aparte: uv sync --group infra)
  uv run cdk deploy                       # CDK en Python, eu-west-1
  ```

**Documentos compañeros** (contexto, no reimplementar): `docs/cuestionario_perfilado.md` (banco de preguntas, caminos y evidencias de M11 — especificación del seed); `docs/competencia_y_ux.md` (investigación de competencia traducida a requisitos: indicador de listo para auditoría, portal del auditor, antipatrones de UI, precio); `docs/evidencias_por_herramienta.md` (qué evidencia acepta un auditor por familia de herramienta, con alternativas, criterios de aceptación y rechazos típicos); `docs/ingesta_ia.md` (M16: casos de uso, límites, privacidad y fases); `docs/plan_construccion.md` (**fases, criterios de cierre y prompts de arranque para Claude Code**); `docs/brief_diseno.md` (**pantallas, estados y sistema visual para Claude Design**); `docs/roles_y_permisos.md` (roles, matriz de permisos, separación de funciones, acceso de soporte y del auditor); `docs/validacion_externa.md` (**guiones para contrastar el seed con auditor, certificadora y cliente piloto — antes de cerrar F4**); `docs/decisiones.md` (**decisiones abiertas con recomendación y plazo: alcance del producto, autenticación, región, precio, marca**); planteamiento de producto, especificación del motor de riesgos, documento de presentación al auditor, y el sistema visual de `docs/brief_diseno.md` §2.

---

## 16. Roadmap de construcción

> ⚠️ **La numeración de fases que manda es la de `docs/plan_construccion.md`**, que es la que usan `ESTRUCTURA.md` y el resto de referencias (validación externa antes de cerrar **F4**, CPSTIC en **F7**). La tabla de abajo es una **agrupación temática** con numeración propia y **no coincide** con ella. Secuencia canónica:
>
> `F0 Cimientos → F1 Catálogo + ens_applicability → F2 Categorización y DdA → F3 Motores (scoring + riesgo) → F4 Perfilado y evidencias → F5 Documental y versionado → F6 Paquete de auditoría + portal del auditor (fin v1) → GATE producción → F7 CPSTIC · F8 Palancas`
>
> Cada fase de `plan_construccion.md` trae entregables, criterios de cierre y su prompt de arranque. No se empieza una fase sin cerrar la anterior.

| Agrupación temática (numeración propia, ver aviso) | Entregable |
|---|---|
| **F0 · Cimientos** | Monorepo (Django + Vue + engines + infra), Aurora, S3 Object Lock, Cognito+MFA, import OSCAL del catálogo ENS (73 medidas, 133 refuerzos, 467 items) + `ens_applicability` con pytest. `tenant_id` (nullable) en modelos de tenant. **Membership/Invitation/AuditLog y `can()` desde la primera migración** (`docs/roles_y_permisos.md`). |
| **F1 · Núcleo cliente** | M1 Categorización (freemium) + M2 DdA + export PDF (WeasyPrint) + **M11 perfilado** con `evidence_engine` y carpeta a medida (vista de huecos). |
| **F1b · CPSTIC** | `cpstic_parser` (guía 105) + staging/diff/revisión en panel admin + snapshot CPSTIC + `SecurityComponent` + rutas op.pl.5 + revalidación mensual. |
| **F2 · Motores** | `scoring_engine` (M6) + `risk_engine` (M7) con pytest; M4 checklist. |
| **F3 · Documental** | M3 generación documental + M8 versionado inmutable. |
| **F4 · Auditoría** | M5 subida/revisión/vigencia de evidencias + M9 paquete 808 con trazabilidad pregunta→evidencia + **M14 portal del auditor** (muestreo y peticiones) + M12 acuses + M13 incidentes/PAC. → **fin de la v1**. |
| **GATE producción** | Aislamiento de tenant completo (§14.3): NOT NULL + managers scoped + RLS + tests negativos. |
| **F5 · Escala (post-v1)** | M10 multi-tenant/consultora + marca blanca + export INES. |
| **F6 · Palancas (post-v1)** | **M16 ingesta asistida por IA** (importar DdA e informe de auditoría previos, clasificar documentos, huecos y contradicciones) · **Mapeo multi-marco** (ENS↔ISO 27001↔ISO 22301↔RGPD↔NIS2) con reutilización de evidencias · **recolectores automáticos** de evidencia vía API (Entra/M365, Google, AWS, consolas EDR) · **riesgo de proveedores** con propagación al riesgo del sistema · **M15 portal de confianza** público para que un proveedor muestre su estado ENS a sus clientes. |

---

## 17. Decisiones abiertas

> Análisis, implicaciones, recomendación y plazo de cada una: **`docs/decisiones.md`**. Las marcadas ⏰ bloquean fases.


- **Stack (lenguaje, API, frontend, IaC):** ✅ DECIDIDO — Django + Django Ninja + Vue + CDK Python (§5).
- **Aislamiento de tenant:** ✅ DECIDIDO — fuera de v1, gate previo a producción; `tenant_id` como andamiaje ya en v1 (§14).
- **IaC:** CDK en Python confirmado; Terraform solo si se prefiere declarativo.
- **UI del frontend:** shadcn-vue (marca) vs PrimeVue (data-grid) — decidir al montar el dashboard.
- **Refuerzos sin props (41):** confirmar contra las tablas del RD 311/2022 que son opcionales. Revisar también las erratas conocidas y reportarlas a la AEAD si procede.
- **Licencia EUPL-1.2 del catálogo:** es copyleft y cubre la comunicación por red. Mantener el JSON sin modificar y separado de la capa propia. Si se modificara, publicar esos cambios bajo EUPL. Validarlo con asesoría legal. El PDF de decisiones es CC BY-NC-SA (no se redistribuye).
- **Export OSCAL:** ✅ la DdA se exporta como **profile** (`engines/oscal_io/export.py`): include/exclude de controles y `set-parameters` para las selecciones. Queda abierto si el paquete de auditoría se exporta además como *assessment-results*, y si hace falta un SSP que importe este profile cuando se publique la implementación.
- **Datos CPSTIC:** extracción solo de campos fácticos (§3.2.0); validar con asesoría (derecho *sui generis* y aviso legal) e informar al CCN antes de producción.
- **Fuente del CPSTIC:** ✅ DECIDIDO (§3.2.1) — no hay formato estructurado; ingesta semiautomática desde la guía CCN-STIC-105 con revisión humana. Si el CCN publica OSCAL/JSON, se sustituye el parser sin tocar el modelo.
- **IA (M16):** proveedor y modelo, acuerdo con retención cero, umbral de confianza por caso de uso y texto para el comprador público sobre el subencargado.
- **Precio y posicionamiento:** propuesta de precio público entre Cumpleo y los packs de consultoría, con renovación garantizada (`docs/competencia_y_ux.md` §6). Validar con 2-3 clientes reales.
- **Marca:** ✅ BLENS verificado libre. Pendiente registrar dominio y valorar marca en la OEPM (clases 9 y 42).
- **Validación con certificadoras:** hablar con 1-2 entidades acreditadas por ENAC sobre qué formato de paquete les ahorra tiempo. Valida M9 y M14.
- **Mapeo multi-marco:** decidir si se compra o se construye el crosswalk ENS↔ISO 27001 (Anexo de la CCN-STIC-825 u otras equivalencias publicadas) y si NIS2 entra como marco propio. **Verificar el estado de la transposición española de NIS2** antes de prometerlo.
- **Recolectores automáticos de evidencia:** valor alto pero cada integración es un subencargado y amplía la superficie de seguridad. Además, el auditor suele pedir la captura con contexto: la recolección automática **complementa**, no sustituye.
- **Motor de reglas:** JSON Logic (propuesto; estándar, portable al frontend para `show_if`) vs mini-DSL propio.
- **Contenido del banco de preguntas y plantillas de evidencia:** redactarlo y revisarlo contra CCN-STIC-808 medida a medida; es el activo principal del producto.
- **Validación asistida por IA de capturas** (¿se ve lo que debe verse?): post-v1; exige proveedor en la UE y figura como subencargado.
- **Revisión por el auditor en la vista auditor** (comentarios, peticiones de evidencia adicional): ¿v1 o post-v1?
- **Alcance de la generación documental:** confirmar el set exacto de plantillas y su nivel de personalización.
