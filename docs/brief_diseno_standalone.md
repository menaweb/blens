# Brief de diseño — para Claude Design

> Documento compañero de `CLAUDE.md`. Qué pantallas hay que diseñar, en qué orden, con qué contenido real y qué estados. Contexto imprescindible: `CLAUDE.md` §5bis (convenciones de UI/UX), `docs/cuestionario_perfilado.md` §1bis (redacción de preguntas) y `docs/competencia_y_ux.md` §3 a §5 (indicador, portal del auditor y antipatrones).

---

## 1. Qué es BLENS y para quién se diseña

Plataforma para cumplir el Esquema Nacional de Seguridad español. El usuario habitual **no es un experto en seguridad**: es el informático de una pyme proveedora de la Administración, o el responsable de seguridad de un ayuntamiento, que tiene que certificarse y no sabe por dónde empezar. Llega asustado y con prisa.

**La promesa visual:** en todo momento el usuario debe ver **dónde está, qué le falta y qué tiene que hacer ahora**. Si una pantalla no responde a esas tres preguntas, sobra.

Tono: sobrio, institucional pero no gris, cercano sin ser informal. Es una herramienta de trabajo que se usa muchas horas, no una app de consumo. Nada de gamificación: que suba un número no significa estar conforme.

---

## 2. Marca y sistema

**No existe landing todavía**, así que estos tokens son el punto de partida y la landing se hará después con ellos. Ajustables, pero una vez fijados se usan en todo.

### Color
| Token | Valor | Uso |
|---|---|---|
| `--brand-900` | `#0B4F4A` | Cabeceras oscuras, texto sobre claro |
| `--brand-700` | `#0F766E` | **Color principal**: botones, enlaces, elementos activos |
| `--brand-500` | `#14A79B` | Acentos, gráficas, estados hover |
| `--brand-100` | `#CCFBF1` | Fondos suaves, resaltados |
| `--brand-50` | `#F0FDFA` | Fondo de sección |
| `--ink-900` | `#0F172A` | Texto principal |
| `--ink-600` | `#475569` | Texto secundario |
| `--ink-400` | `#94A3B8` | Texto deshabilitado, bordes |
| `--surface` | `#FFFFFF` / `#F8FAFC` | Fondo de tarjeta y de página |

**Semánticos** (nunca solos: siempre con icono o texto):
`--ok #15803D` cumple · `--warn #B45309` insuficiente · `--danger #B91C1C` crítico · `--muted #64748B` no aplica · `--info #1D4ED8` informativo · `--expired #7C2D12` caducado (distinto del rojo crítico) · `--ai #7C3AED` sugerido por IA.

El teal es el color de la marca y de la acción. **El verde semántico nunca es el teal**, para que "es un botón" y "esto cumple" no se confundan.

### Tipografía
- **Interfaz:** Inter, con `font-feature-settings: "tnum"` activado. Hay muchas tablas y porcentajes y los números tienen que alinearse.
- **Códigos de medida** (`op.exp.6`, `CHK-op.acc.4.2`): monoespaciada (JetBrains Mono o la del sistema). Aparecen constantemente y deben reconocerse de un vistazo.
- **Escala:** 12 / 14 / 16 / 20 / 24 / 32. El cuerpo de tabla a 14, la pregunta del perfilado a 20.

### Espaciado y forma
- Rejilla de 4 px. Radio 8 px en tarjetas y 6 px en controles. Sombras suaves, nada de relieve marcado.
- Ancho máximo de lectura en el perfilado: 680 px. Las tablas ocupan todo el ancho.
- **Densidad:** alta en tablas y listados, con opción de vista cómoda. Esto es una herramienta de datos.
- **Accesibilidad WCAG AA:** contraste, foco visible, uso completo con teclado (también en el grafo y las tablas), `prefers-reduced-motion`.
- **Idioma:** español. Preparar para más idiomas, sin prioridad.
- **Móvil:** la app es de escritorio, con dos excepciones que sí deben funcionar bien en el móvil: **subir evidencias** (hacer la foto del CPD o del extintor en el sitio) y **consultar el estado**.

---

## 3. Estados que toda pantalla debe contemplar

Se diseñan explícitamente, no se improvisan:

1. **Vacío de verdad** (cliente nuevo, sin nada): es la primera impresión y la que más convierte. Tiene que decir qué hacer, no lamentar que no haya datos.
2. **Cargando** (hay cálculos y tareas en segundo plano: PDF, ZIP, recálculos).
3. **Error** con salida: qué pasó y qué puede hacer.
4. **Caducado:** una evidencia o un certificado que venció. Estado propio, no un rojo genérico.
5. **Pendiente de revisión** y **rechazado con motivo**.
6. **Sugerido por IA:** distintivo claro, con confianza y origen, y acción de aceptar o corregir. Nunca se confunde con un dato confirmado.
7. **No aplica justificado:** visible, no escondido.

---

## 4. Estructura de navegación

Barra lateral con las secciones, y arriba el selector de sistema (un cliente puede tener varios) y el indicador de listo para auditoría siempre visible.

```
Inicio (dashboard)
Mi sistema
  ├─ Categorización
  ├─ Declaración de Aplicabilidad
  └─ Perfilado
Cumplimiento
  ├─ Medidas (checklist)
  └─ Evidencias (la carpeta)
Riesgos
  ├─ Activos y dependencias
  └─ Amenazas y tratamiento
Documentos
Componentes y proveedores
Incidentes y acciones
Auditoría
  ├─ Paquete
  └─ Acceso del auditor

Menú de la cuenta (arriba a la derecha, fuera de la barra lateral)
  ├─ Mi perfil y seguridad (contraseña, segundo factor, sesiones)
  ├─ Usuarios y roles
  ├─ Mi actividad
  └─ Plan y facturación
```

Fuera de la aplicación, sin barra lateral: categorización sin cuenta, crear cuenta, iniciar sesión, recuperar contraseña, aceptar invitación y el portal del auditor.

---

## 5. Pantallas a diseñar, por prioridad

### Prioridad 1 — lo que convierte y lo que se usa a diario

**P1. Categorización gratuita (sin cuenta)**
Asistente de 5 pasos, uno por dimensión. Cada paso: una pregunta en lenguaje llano con ejemplos reconocibles, y cuatro opciones (no aplica, bajo, medio, alto). Resultado: categoría resultante, número de medidas aplicables y qué implica. Llamada a la acción para guardar el resultado creando cuenta. Debe verse serio y rápido: es la puerta del producto.

**P2. Perfilado (el corazón)**
- Lista de bloques con progreso, minutos estimados y responsable asignado.
- Ficha de pregunta: texto grande, **por qué se pregunta**, **dónde mirarlo** (con la ruta de menús de las herramientas que el propio cliente ya declaró), opciones como situaciones reales, y glosario al pasar el ratón.
- Botón secundario **"preguntárselo a otra persona"** que pide a quién y crea la tarea. No existe la opción "no lo sé" en el menú.
- Al responder algo que abre camino (por ejemplo, declarar un CPD propio), se ve aparecer el bloque nuevo: el usuario entiende por qué crece el cuestionario.
- Guardado automático visible y posibilidad de salir y volver.

**P3. La carpeta de evidencias**
El objeto central del producto. Dos vistas de lo mismo:
- **Árbol de carpetas** con la estructura del paquete de auditoría (00_Gobernanza, 01_Alcance…), con su estado por carpeta.
- **Lista de requisitos** filtrable por marco, familia, estado, responsable y "caduca pronto".
Cada fila: qué se pide, medida a la que responde, estado, responsable y vencimiento.

**P4. Detalle de un requisito de evidencia**
Aquí se gana o se pierde la usabilidad:
- Qué hay que demostrar y a qué medida o requisito responde.
- **Opciones alternativas** ordenadas por solidez ("con una basta"), con la preferida destacada.
- **Qué debe verse:** lista de criterios marcables.
- **Rechazos típicos** como aviso antes de subir, no después.
- Zona de subida (arrastrar, o cámara en móvil), con la ruta concreta para su producto.
- Historial: versiones, quién subió, quién validó, fecha de caducidad.

**P5. Dashboard**
- **Indicador de listo para auditoría** con sus **tres componentes separados** (madurez suficiente, evidencia viva, documentación vigente). Debajo, en texto pequeño pero claro: esto no es una declaración de conformidad.
- Heat-map por familia y marco.
- Ranking de gaps con acción directa.
- Delta desde la semana anterior.
- Avisos agrupados: evidencias que caducan, certificados de proveedor que vencen, tareas vencidas.

### Prioridad 1b — cuenta y acceso (el puente entre el gancho y el producto)

Son pantallas de prioridad 1 por lo que se juegan, aunque se diseñen después del camino principal: si el paso de "he obtenido mi categoría" a "tengo una cuenta con mi sistema dentro" se rompe, el gancho gratuito no convierte nada. La identidad la gestiona Cognito (D1 de `docs/decisiones.md`), pero **las pantallas son nuestras**: nada de la Hosted UI de AWS, que rompería la marca y, sobre todo, impediría enseñar el resultado de la categorización encima del formulario de alta. Correo y contraseña, con segundo factor. No hay botón de "entrar con Google" ni de Cl@ve, y conviene que el diseño no lo insinúe.

**P16. Crear cuenta desde el resultado de la categorización.** Continuación natural de P1, no un formulario que aparece de la nada: arriba, el resultado que la persona acaba de obtener (categoría y niveles), para que vea qué está guardando. Debajo, los datos mínimos: organización, nombre, correo y contraseña. Después, verificación del correo y aterrizaje directo en su sistema ya creado. Estado a contemplar: **el resultado anónimo ha caducado** — el alta sigue adelante y se explica sin culpar a nadie que hay que repetir la categorización, que son dos minutos.

**P17. Iniciar sesión, segundo factor y recuperar contraseña.** Tres pantallas sobrias de la misma familia. En el segundo factor: alta con código QR y verificación. **No hay códigos de recuperación** —Cognito no los da—, así que hace falta una salida diseñada para quien pierde el móvil: pedir a un administrador de su organización que se lo restablezca, dicho sin dramatismo y sin dejarle en un callejón. Errores concretos y sin pistas de más: nunca "ese correo no existe". Estado propio para la cuenta bloqueada por intentos fallidos.

**P18. Aceptar una invitación.** La ve alguien que no conoce BLENS y a quien un compañero ha metido en esto. Tiene que decir en una pantalla quién le invita, a qué organización, con qué papel y qué se espera de él, antes de pedirle que elija contraseña. Estados: invitación caducada, ya usada o revocada, cada uno con salida clara.

**P19. Usuarios y roles.** Tabla de miembros con rol, sistemas a los que alcanza, estado e invitaciones pendientes. Incluye **restablecer el segundo factor** de un miembro que ha perdido el suyo, con confirmación y traza: es la contrapartida de que no haya códigos de recuperación. Invitar abre un panel con rol, ámbito de sistemas y bloques del perfilado. Los accesos temporales de auditor y consultor se ven con su **fecha de caducidad destacada**. Acciones delicadas —revocar, cambiar de rol, transferir la propiedad— con confirmación que explica la consecuencia. El sistema impide dejar la organización sin propietario, y el diseño debe explicar por qué, no solo desactivar el botón.

**P20. Mi perfil y seguridad.** Datos personales, contraseña, segundo factor, sesiones activas y **mi actividad**: qué he hecho yo, con fecha. Es lo que convierte el registro encadenado en algo útil para el usuario, y no solo en un requisito de op.exp.8.

**P21. Plan y facturación** (se diseña cuando se cierre el precio, D3). Plan actual, límites, cambio de plan y facturas. No se diseña antes de saber qué se cobra.

### Prioridad 2 — trabajo de fondo

**P6. Checklist de medidas.** Tabla densa: medida, aplicable, madurez actual y objetivo, delta con semáforo, responsable, fecha, evidencias enlazadas y aviso de "madurez no soportada". Filtros y edición en línea, con navegación por teclado.

**P7. Declaración de Aplicabilidad.** Tabla de medidas y refuerzos con su origen de aplicabilidad (categoría o nivel de dimensión), selecciones de refuerzo a resolver, no aplicables con justificación obligatoria, y flujo de aprobación con versión.

**P8. Riesgos: activos y dependencias.** El grafo es donde la competencia falla, así que hay que hacerlo bien: multiselección de nodos, **porcentaje de dependencia visible en la arista**, zoom y desplazamiento fluidos, autoajuste, detección de ciclos con mensaje claro, y alternativa en tabla para quien prefiera teclado.

**P9. Riesgos: amenazas y tratamiento.** Por amenaza y dimensión: riesgo intrínseco frente a residual, lado a lado, con las salvaguardas que lo reducen y su madurez. **Simulador**: "si subo op.mon.1 a L4, el riesgo baja a X". Decisión de tratamiento con responsable y plazo.

**P10. Componentes y proveedores.** Lista de componentes de seguridad con su ruta de op.pl.5 (CPSTIC, certificado del artículo 19 o compensatoria), versión, caducidad de la cualificación y avisos. Proveedores con su certificado ENS, alcance y vigencia.

**P11. Documentos.** Lista por tipo con estado (borrador, en revisión, aprobado, vigente, obsoleto), versiones, diff y descargas. Editor sencillo del documento generado.

**P12. Incidentes y plan de acciones.** Registro de incidentes y lista de hallazgos con responsable, plazo y estado.

### Prioridad 3 — específicas

**P13. Portal del auditor.** Interfaz **distinta y minimalista**, sin el resto de la aplicación. Por medida: checks, evidencias con fecha y procedencia, documentos vigentes. Herramienta de muestreo, peticiones de información y marcado de revisado. Debe transmitir rigor y no hacerle perder un minuto: es quien decide si tu cliente se certifica.

**P14. Panel de administración del CPSTIC** (interno): subida de la guía, diff del mes con altas, bajas y dudosas, y aprobación.

**P15. Página pública de confianza** (post-v1): estado ENS del cliente para enseñar en licitaciones.

---

## 6. Piezas reutilizables que conviene resolver una vez

- **Semáforo de madurez** (L0-L5 con objetivo y delta).
- **Chip de estado de evidencia:** pendiente, aportada, en revisión, validada, rechazada, caducada, fuera de alcance, no aplica.
- **Tarjeta de pregunta** del perfilado, con sus cuatro apoyos.
- **Bloque de criterios de aceptación** marcable.
- **Aviso de rechazo típico** (preventivo, no alarmista).
- **Distintivo de sugerencia de IA** con nivel de confianza y enlace al origen.
- **Selector de sistema** y migas de pan.
- **Panel de tarea en segundo plano** (generando PDF, ZIP o recalculando).
- **Tabla de datos** con filtros, orden, densidad y export.

---

## 7. Textos de ejemplo reales (usar estos, no *lorem ipsum*)

Pregunta del perfilado:
> **¿Los ordenadores y servidores tienen antivirus?**
> *Por qué:* el auditor comprobará que están protegidos todos, y que el antivirus está actualizado y alguien mira sus avisos.
> *Cómo saberlo:* si usáis Microsoft 365, entrad en el portal de Defender, en Dispositivos.
> Opciones: uno contratado · el que trae Windows · solo en algunos equipos · lo gestiona nuestro proveedor · no hay antivirus

Requisito de evidencia:
> **Inventario de la consola del antivirus** · op.exp.6 · caduca en 90 días
> Con una de estas tres basta: export de la consola (preferida), captura del panel de cobertura, o informe del proveedor.
> Debe verse: el total de equipos protegidos · que coincide con el inventario · que incluye servidores · sin equipos sin comunicar.
> El auditor lo rechazará si: es la captura de un solo equipo, o si la cobertura es del 80 % sin explicar el 20 % restante.

Estado vacío del dashboard:
> **Aún no hay datos de cumplimiento.** Empieza por categorizar tu sistema: son 5 preguntas y 2 minutos, y de ahí sale todo lo demás.

---

## 8. Lo que NO se debe diseñar

- Insignias, medallas, celebraciones ni barras que sugieran que ya se cumple.
- Rojos alarmistas por todas partes en el primer uso: un cliente nuevo está a cero por definición y eso es normal.
- Menús duplicados ni un "modo experto" que solo cambie de sitio las mismas opciones.
- Pantallas que exijan entender el ENS para usarse.
- Notificaciones sueltas por cada cambio: van agrupadas y accionables.

---

## 9. Prompts de arranque para Claude Design

**Pantalla 1 · Categorización gratuita**
> Lee `docs/brief_diseno.md` (§2 tokens, §3 estados) y `docs/cuestionario_perfilado.md` §1bis. Diseña el asistente de categorización de BLENS: 5 pasos, uno por dimensión (confidencialidad, integridad, disponibilidad, autenticidad, trazabilidad), con cuatro opciones cada uno (no aplica, bajo, medio, alto) y ejemplos reconocibles. Más la pantalla de resultado con la categoría obtenida, el número de medidas aplicables y la llamada a crear cuenta. Se usa sin registro y es la puerta del producto: tiene que transmitir seriedad y rapidez. Nada de gamificación.

**Pantalla 1b · Crear cuenta y aceptar invitación**
> Lee `docs/brief_diseno.md` §5 (P16 a P20) y `docs/roles_y_permisos.md`. Diseña el puente entre la categorización gratuita y el producto: crear cuenta mostrando arriba el resultado recién obtenido, verificación del correo, iniciar sesión, alta del segundo factor con QR, y aceptar una invitación explicando quién invita, a qué organización y con qué papel. Correo y contraseña sobre Cognito, pero con **pantallas nuestras: no uses la Hosted UI de AWS** ni botones de proveedores externos. Incluye los estados incómodos, que son la mitad del trabajo: resultado anónimo caducado, invitación caducada o ya usada, cuenta bloqueada por intentos fallidos y segundo factor perdido. Tono sobrio; quien llega aquí acaba de decidir fiarse.

**Pantalla 2 · Ficha de pregunta del perfilado**
> Usa el ejemplo real del antivirus de `docs/cuestionario_perfilado.md` §1bis. Diseña la pantalla de una pregunta con sus cuatro apoyos: el texto, el porqué, dónde mirarlo y las opciones como situaciones reales, más glosario al pasar el ratón. Incluye el botón secundario "preguntárselo a otra persona" (no existe la opción "no lo sé") y la barra de progreso por bloques con minutos estimados y responsable asignado.

**Pantalla 3 · Detalle de requisito de evidencia**
> Usa el ejemplo del inventario de la consola del antivirus de `docs/brief_diseno.md` §7. Diseña la pantalla de un requisito: qué hay que demostrar, las tres opciones alternativas ordenadas por solidez con la preferida destacada, los criterios marcables de "qué debe verse", el aviso de rechazos típicos antes de subir, la zona de subida y el historial con estado y caducidad.

**Pantalla 4 · Dashboard**
> Diseña el panel principal con el indicador "listo para auditoría" y sus tres componentes separados (madurez suficiente, evidencia viva, documentación vigente), el heat-map por familia y marco, el ranking de carencias con acción directa y los avisos agrupados. Incluye el estado vacío de un cliente nuevo, que es la primera impresión. Recuerda: el indicador no es una declaración de conformidad y el diseño debe decirlo sin alarmar a quien acaba de empezar.

---

## 10. Material de referencia incluido (no hace falta ningún otro fichero)

### 10.1 Indicador "listo para auditoría" (pantalla 4)
Un solo número con **tres componentes visibles por separado**:
1. **Madurez suficiente:** medidas cuyo nivel alcanza el umbral de su categoría (Básica L2, Media L3, Alta L4).
2. **Evidencia viva:** requisitos obligatorios con evidencia validada y no caducada.
3. **Documentación vigente:** documentos obligatorios aprobados y en vigor.

Reglas que el diseño debe reflejar:
- Una medida con madurez declarada pero sin evidencia validada se marca **"madurez no soportada"** y no suma.
- Nunca se redondea al alza.
- Debajo, en texto pequeño pero claro: esto **no es una declaración de conformidad**; la conformidad la declara el auditor.
- Sin insignias, medallas ni celebraciones.

### 10.2 Ficha de pregunta completa (pantalla 2), texto real
> **¿Los ordenadores y servidores tienen antivirus?**
>
> **Por qué se pregunta:** el auditor comprobará que están protegidos **todos**, y que el antivirus está actualizado y alguien mira sus avisos.
>
> **Cómo saberlo:** si usáis Microsoft 365, entrad en el portal de Defender, en Dispositivos. Si tenéis otro (ESET, Sophos, CrowdStrike, SentinelOne), su consola muestra cuántos equipos aparecen.
>
> **Opciones:** Uno contratado · El que trae Windows · Solo en algunos equipos · Lo gestiona nuestro proveedor · No hay antivirus
>
> **Glosario (al pasar el ratón sobre "EDR"):** antivirus avanzado que además vigila comportamientos sospechosos y permite responder en remoto.
>
> **Botón secundario:** "Preguntárselo a otra persona" → pide a quién y crea una tarea. **No existe la opción "no lo sé" en el menú.**
>
> **Pregunta siguiente encadenada:** ¿cuántos equipos hay en total y cuántos aparecen en la consola?

Bloques del cuestionario con su progreso, para la barra lateral: Organización y alcance · Servicios e información · Gobernanza · Dónde vive el sistema · Instalaciones · Proveedores y nube · Inventario · Identidades y acceso · Puestos · Explotación · Red · Registro e incidentes · Copias y continuidad · Información y soportes · Desarrollo · Servicios expuestos · Personas · Estado de cumplimiento.

### 10.3 Requisito de evidencia completo (pantalla 3), texto real
> **Inventario de la consola del antivirus** · medida op.exp.6 · caduca en 90 días · responsable: [persona] · estado: pendiente
>
> **Con una de estas tres basta:**
> 1. *(preferida)* Export de la consola con el listado de equipos y su estado de protección.
> 2. Captura del panel de cobertura con los totales.
> 3. Informe del proveedor que gestiona el servicio, fechado y en su papelería.
>
> **Qué debe verse** (casillas marcables):
> - Se ve el total de equipos protegidos
> - Coincide con el total del inventario, o se explica la diferencia
> - Incluye servidores, no solo puestos
> - No hay equipos sin comunicar desde hace semanas
>
> **El auditor lo rechazará si:** es la captura de un solo equipo · la cobertura es del 80 % sin explicar el 20 % restante · hay equipos inactivos desde hace meses.
>
> **Dónde encontrarlo en tu herramienta:** Portal de Defender → Activos → Dispositivos → Exportar.

### 10.4 Estructura de la carpeta de evidencias (pantalla 3, vista de árbol)
```
00_Gobernanza/            01_Alcance_y_Categorizacion/   02_Analisis_de_Riesgos/
03_Declaracion_de_Aplicabilidad/                          04_[org]/
05_[op]/                  06_[mp]/                       07_Auditoria_y_Mejora/
99_Indice/
```
Cada carpeta muestra su estado: cuántos requisitos tiene, cuántos resueltos y cuántos caducan pronto.

### 10.5 Escala de madurez (pantallas 4 y checklist)
L0 inexistente · L1 inicial · L2 repetible · L3 definido · L4 gestionado · L5 optimizado.
Se muestra siempre **nivel actual frente a objetivo** y la diferencia, con semáforo: verde si falta menos de un nivel, ámbar entre uno y dos, rojo a partir de dos.

### 10.6 Vocabulario (usar estas palabras, no otras)
Medida · refuerzo · Declaración de Aplicabilidad · categoría (Básica, Media, Alta) · dimensiones (confidencialidad, integridad, disponibilidad, autenticidad, trazabilidad) · evidencia · requisito · check · madurez · paquete de auditoría.
Evitar: "control" (es vocabulario ISO, no ENS), "compliance", "score", "gap" en la interfaz (en el texto de trabajo sí).
