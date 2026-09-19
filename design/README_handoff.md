# Handoff: BLENS — plataforma de cumplimiento del ENS

## Cómo usar esto junto a tu CLAUDE.md

Este documento describe **qué** hay que construir y **cómo debe verse y comportarse**. Tu `CLAUDE.md` manda en **cómo se escribe el código**: arquitectura, convenciones, librerías, nomenclatura, pruebas y flujo de trabajo.

Regla de precedencia ante conflicto:
- Decisiones visuales y de comportamiento (colores, escalas, textos, estados, reglas de producto) → este README.
- Decisiones técnicas (framework, estructura de carpetas, estado global, estilos, testing) → tu `CLAUDE.md`.
- Si tu `CLAUDE.md` ya define un sistema de diseño propio, mapea los tokens de aquí a los tuyos en lugar de duplicarlos, y documenta la equivalencia una sola vez.

Sugerencia de arranque en Claude Code:

> Lee `CLAUDE.md` y `design_handoff_blens/README.md`. Implementa la pantalla «Perfilado, ficha de pregunta» siguiendo las convenciones de CLAUDE.md y la especificación visual del handoff. Antes de escribir código, dime qué tokens del handoff mapeas a los del proyecto y qué piezas reutilizables vas a crear.

Las piezas que conviene resolver una sola vez, porque se repiten en casi todas las pantallas: semáforo de madurez (L0–L5 con objetivo y delta), chip de estado de evidencia, tarjeta de pregunta del perfilado, bloque de criterios marcables, aviso de rechazo típico, distintivo de sugerencia de IA, selector de sistema con migas, panel de tarea en segundo plano y tabla de datos con filtros, orden, densidad y export.

## Visión general

BLENS es una plataforma web para que organizaciones españolas (pymes proveedoras de la Administración y entidades locales) cumplan el Esquema Nacional de Seguridad, regulado por el RD 311/2022. El usuario habitual no es experto en seguridad: es el informático de una pyme o el responsable de seguridad de un ayuntamiento, que llega con prisa y sin saber por dónde empezar.

La promesa de producto, que condiciona cada pantalla: en todo momento el usuario debe ver **dónde está, qué le falta y qué tiene que hacer ahora**.

Este paquete contiene 18 prototipos de escritorio y móvil que cubren el flujo completo: desde la categorización sin cuenta hasta el paquete de auditoría y el portal del auditor.

## Sobre los ficheros de diseño

Los ficheros de `prototipos/` son **referencias de diseño hechas en HTML**: muestran el aspecto y el comportamiento previstos, no son código de producción para copiar tal cual. La tarea es **recrear estos diseños en el entorno del código destino** (React, Vue, Svelte, lo que use el proyecto) con sus patrones y librerías. Si todavía no hay entorno, elige el framework más adecuado e implementa los diseños allí.

Detalles técnicos de los prototipos, que **no** deben trasladarse:
- Cada `.dc.html` es un componente autónomo con estilos en línea y un `support.js` propio del entorno de prototipado. En producción, usa el sistema de estilos del proyecto.
- Los datos son de ejemplo (Ayuntamiento de Valverde, sede electrónica, categoría Media) y están escritos a mano dentro de cada fichero. En producción vienen de la API.
- Los cálculos (indicador, riesgo residual, propagación de dependencias) son aproximaciones para que el prototipo reaccione; las fórmulas reales las define el equipo de producto.

## Fidelidad

**Alta fidelidad.** Colores, tipografía, escalas, estados y textos son definitivos y deben respetarse. Los textos en español son los que hay que usar: el vocabulario del ENS es parte del producto (ver «Vocabulario»).

## Design tokens

### Color

| Token | Valor | Uso |
|---|---|---|
| `--brand-900` | `#0B4F4A` | Cabeceras oscuras, texto de marca sobre claro |
| `--brand-700` | `#0F766E` | **Color principal**: botones, enlaces, elementos activos |
| `--brand-500` | `#14A79B` | Acentos, gráficas, estados hover |
| `--brand-100` | `#CCFBF1` | Fondos suaves, bordes de resaltado |
| `--brand-50` | `#F0FDFA` | Fondo de sección y de fila activa |
| `--ink-900` | `#0F172A` | Texto principal |
| `--ink-600` | `#475569` | Texto secundario |
| `--ink-400` | `#94A3B8` | Deshabilitado, bordes discontinuos |
| `--surface` | `#FFFFFF` | Fondo de tarjeta |
| `--surface-alt` | `#F8FAFC` | Fondo de página y de cabecera de tabla |
| `--border` | `#E2E8F0` | Bordes de tarjeta, tabla y control |
| `--border-soft` | `#F1F5F9` | Separadores interiores de fila |

**Semánticos** (nunca solos: siempre con icono o texto):

| Token | Valor | Fondo | Significado |
|---|---|---|---|
| `--ok` | `#15803D` | `#F0FDF4` | cumple, validado, vigente |
| `--warn` | `#B45309` | `#FFFBEB` | insuficiente, vence pronto, sin resolver |
| `--danger` | `#B91C1C` | `#FEF2F2` | crítico, rechazado, vencido |
| `--muted` | `#64748B` | `#F8FAFC` | no aplica, sin datos |
| `--info` | `#1D4ED8` | `#EFF6FF` | informativo, en revisión |
| `--expired` | `#7C2D12` | `#FEF6F0` | caducado (distinto del rojo crítico) |
| `--ai` | `#7C3AED` | `#F5F3FF` | sugerido por IA |
| `--chart-warn` | `#CA8A04` | — | tramo intermedio en gráficas (solo relleno, nunca texto) |

Reglas de color de obligado cumplimiento:
- El teal es el color de la marca y de la acción. **El verde semántico nunca es el teal**, para que «es un botón» y «esto cumple» no se confundan.
- Los chips semánticos llevan borde del mismo color al 20 % de opacidad (`color + "33"` en hexadecimal).
- `#CA8A04` solo como relleno de gráfica; como texto no cumple AA.
- Caducado (`#7C2D12`) es un estado propio, no un rojo crítico.

### Tipografía

- **Interfaz:** Inter, con `font-feature-settings: "tnum"` activado globalmente (hay muchas tablas y porcentajes y los números tienen que alinearse).
- **Códigos de medida** (`op.exp.6`, `CHK-op.acc.4.2`, rutas de carpeta, huellas SHA): JetBrains Mono.
- **Escala:** 12 / 13 / 14 / 16 / 20 / 24 / 32 px.
  - 12: metadatos, chips, pies de tabla, ayudas.
  - 13: texto secundario denso, botones pequeños, listas laterales.
  - 14: cuerpo de tabla, párrafos, títulos de sección.
  - 16: títulos de tarjeta, opciones de respuesta.
  - 20: pregunta del perfilado, título de pantalla secundaria.
  - 24: título de pantalla, cifras destacadas.
  - 32: indicador principal, categoría resultante.
- Pesos: 400 normal, 500 semidestacado, 600 títulos y cifras. No se usa 700 salvo en marcas de una letra.
- `letter-spacing: -0.01em` en 20 y 24; `-0.02em` en 32. Antetítulos en 12 con `letter-spacing: 0.06em` y versalitas.
- `line-height`: 1.3 en títulos, 1.45–1.6 en cuerpo.

### Espaciado, forma y sombra

- Rejilla de 4 px. Valores usados: 2, 3, 4, 6, 8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 64.
- Radio: 5 px en chips, 6 px en controles y botones, 8 px en tarjetas y tablas, 28 px en marcos de móvil, 50 % en círculos.
- Sombras, solo tres:
  - Tarjeta: `0 1px 2px rgba(15,23,42,0.04)`.
  - Panel flotante o popover: `0 12px 28px rgba(15,23,42,0.16)`.
  - Modal: `0 24px 64px rgba(15,23,42,0.28)`. Fondo del modal: `rgba(15,23,42,0.45)`.
- Ancho máximo de lectura en el perfilado: 680 px. Contenido general: 1240 px. Tablas a todo el ancho.
- Barra lateral: 286–340 px según pantalla. Cabecera: 56 px.

### Accesibilidad

- WCAG AA: contraste mínimo 4.5:1 en texto. No usar `--ink-400` para texto de contenido; es para bordes y deshabilitado.
- Foco visible: `outline: 2px solid #0F766E; outline-offset: 1–2px`.
- Uso completo con teclado, incluidas tablas y grafo (el grafo tiene alternativa en tabla).
- `prefers-reduced-motion: reduce` desactiva transiciones.
- Objetivos táctiles de 44 px mínimo en las vistas móviles.
- Idioma español, preparado para más idiomas.

## Navegación

```
Inicio (dashboard)
Mi sistema
  ├─ Categorización
  ├─ Declaración de Aplicabilidad
  └─ Perfilado
Cumplimiento
  ├─ Medidas (checklist)
  └─ Evidencias (carpeta) → Detalle de requisito
Riesgos
  ├─ Activos y dependencias
  └─ Amenazas y tratamiento
Documentos
Componentes y proveedores
Incidentes y acciones
Auditoría
  ├─ Paquete
  └─ Acceso del auditor
```

Arriba de la barra lateral, siempre visibles: el selector de sistema (un cliente puede tener varios) y el indicador de listo para auditoría.

Fuera de la aplicación del cliente: el panel interno de administración del CPSTIC y la página pública de confianza.

## Pantallas

### 1. Categorización — `Categorizacion.dc.html`
**Propósito:** asistente de 5 pasos, uno por dimensión, que se usa sin cuenta. Es la puerta del producto.
**Layout:** columna centrada de 680 px. Barra de 5 segmentos arriba, tarjeta blanca con la pregunta y las opciones, pie con Atrás y Siguiente.
**Componentes:** antetítulo «Dimensión N de 5 · nombre»; pregunta a 20/600; ayuda a 14 en `--ink-600`; cuatro opciones como tarjetas con radio de 18 px, título a 14/600 y ejemplo a 13; botón primario deshabilitado (`--muted`) hasta elegir.
**Resultado:** categoría a 32 px, razón («por autenticidad y trazabilidad»), párrafo de implicación (nivel de madurez exigido y si requiere auditoría por entidad acreditada), tres cifras (medidas aplicables, evidencias, documentos), desglose por dimensión con chips, y bloque teal oscuro con «Crear cuenta y guardar» y «Descargar en PDF».
**Reglas:** la categoría es la más alta de las cinco dimensiones. Si las cinco son «no aplica», no hay categoría: se muestra «sin determinar» y un aviso de que el alcance está mal delimitado, sin cifras ni llamada a registro.
**Pendiente:** las cifras por categoría (53/73/91 medidas) son inventadas; sustituir por las del RD 311/2022.

### 2. Perfilado, ficha de pregunta — `Perfilado - Ficha de pregunta.dc.html`
**Propósito:** el corazón del producto. La pantalla que más veces verá el usuario.
**Layout:** barra lateral de 296 px con los 18 bloques del cuestionario (progreso, minutos estimados, iniciales del responsable); columna central de 680 px; cabecera con migas, estado de guardado y «Guardar y salir».
**Los cuatro apoyos de cada pregunta:** texto de la pregunta (20/600); «Por qué se pregunta»; «Cómo saberlo», con la ruta concreta de la herramienta que el cliente declaró (chip monoespaciado `Portal de Defender → Activos → Dispositivos`); y las opciones como situaciones reales.
**Glosario:** términos con subrayado punteado y `cursor: help`; al pasar el ratón, tarjeta oscura de 260 px anclada a la derecha para no salirse del contenedor.
**Botón secundario:** «Preguntárselo a otra persona» abre un panel con lista de personas, nota opcional y «Crear tarea y seguir». **No existe la opción «no lo sé».** Al crear la tarea, la pregunta queda pendiente de terceros con opción de deshacer.
**Guardado automático:** tres estados (activo, «Guardando…», «Guardado a las HH:MM») con punto de color.
**Encadenado:** al responder algo que abre camino, aparece el aviso de que se añade una pregunta al bloque.

### 3. Detalle de requisito de evidencia — `Requisito de evidencia.dc.html`
**Propósito:** que la evidencia se aporte bien a la primera.
**Componentes:** tres opciones alternativas ordenadas por solidez, con la preferida etiquetada; criterios marcables de «qué debe verse» con contador; aviso de rechazos típicos **antes** de la zona de subida; zona de arrastre con «Enviar enlace al móvil»; progreso de subida con salida (enviar a revisión, sustituir, quitar); nota para el auditor con contador de 600 caracteres y estado «Visible para el auditor»; historial con validada, caducada y rechazada con motivo. Panel lateral de 272 px con ficha, sugerencia de IA (distintivo morado con confianza y origen) y «Marcar como no aplica» con justificación obligatoria.

### 4. Carpeta de evidencias — `Carpeta de evidencias.dc.html`
**Propósito:** el objeto central del producto, en dos vistas del mismo contenido.
**Árbol:** las nueve carpetas del paquete (`00_Gobernanza` … `99_Indice`) con resueltos sobre total, barra de progreso, aviso de cuántas caducan pronto y despliegue con sus requisitos.
**Lista:** tabla filtrable (todos, caduca pronto, pendientes, en revisión, rechazados, no aplican) con qué se pide, carpeta, medida, responsable, vencimiento y estado; exportar y conmutador de densidad.
**Cabecera:** cuatro totales, con caducan y rechazados marcados por borde izquierdo de color.

### 5. Dashboard — `Dashboard.dc.html`
**Indicador de listo para auditoría:** un número a 32 px con sus **tres componentes separados**: madurez suficiente, evidencia viva y documentación vigente, cada uno con su barra y su explicación. Delta semanal. Debajo, en 12 px: «Esto no es una declaración de conformidad: la conformidad la declara el auditor. El indicador nunca redondea al alza.»
**Heat-map:** una fila por familia (código monoespaciado + nombre), una celda por medida aplicable, con cuatro estados: sin datos `#CBD5E1`, a más de dos niveles `#B91C1C`, a uno o dos `#CA8A04`, en objetivo `#15803D`.
**Ranking:** «Dónde se pierde más», con impacto en puntos y acción directa; incluye la etiqueta «madurez no soportada».
**Avisos agrupados:** evidencias que caducan, certificados de proveedor y tareas vencidas. Nunca una notificación por cambio.
**Estado vacío:** «Aún no hay datos de cumplimiento.» + los tres pasos siguientes + «Empezar a cero es lo normal. Nadie cumple el ENS el primer día.» En este estado, el botón de cabecera es «Categorizar el sistema», no «Generar paquete».

### 6. Checklist de medidas — `Checklist de medidas.dc.html`
Tabla densa con edición en línea: medida, aplicable (conmutable), madurez actual (selector L0–L5), objetivo, delta con semáforo (verde si falta menos de un nivel, ámbar uno o dos, rojo a partir de dos), evidencias enlazadas y responsable con fecha. Las medidas que alcanzan el umbral sin evidencia validada salen en ámbar con «madurez no soportada: sin evidencia validada, no suma al indicador» y tienen filtro propio. Los contadores de filtro se recalculan al editar. Vista densa o cómoda.

### 7. Declaración de Aplicabilidad — `Declaracion de Aplicabilidad.dc.html`
Tabla de medidas y refuerzos con el **origen de la aplicabilidad** (categoría o nivel de una dimensión concreta), decisión en línea (aplica / no aplica / por decidir) y justificación obligatoria que solo aparece al marcar no aplica. Los refuerzos con selección abierta indican las alternativas. El envío a aprobación se bloquea mientras haya decisiones pendientes o justificaciones vacías, con atajos que filtran a lo que falta. Si el borrador deja de ser aprobable estando en firma, el banner lo dice y permite retirarlo. Historial de versiones con vigente y sustituidas.

### 8. Activos y dependencias — `Activos y dependencias.dc.html`
Grafo en SVG (líneas y cajas) con una capa HTML superpuesta para las etiquetas, proyectada con la misma escala y centrado que aplica el `viewBox` (medir el contenedor con `ResizeObserver`; no usar porcentajes lineales o se desalinean).
Diez activos tipificados por color; porcentaje de dependencia visible en cada arista, con trazo discontinuo por debajo del 50 %; la etiqueta busca un punto libre del recorrido (50 %, si no 32 %, 68 %…) para no caer sobre una caja. Selección simple y múltiple (mayúsculas o cmd), arrastre, rueda, acercar, alejar y autoajustar. Panel lateral con el impacto propagado. **Detección de ciclos** por búsqueda en profundidad, con mensaje en lenguaje llano y las aristas implicadas resaltadas en la tabla. La propagación corta por camino recorrido: sin eso, un ciclo desborda la pila.

### 9. Amenazas y tratamiento — `Amenazas y tratamiento.dc.html`
Lista de amenazas ordenada por riesgo residual descendente. Por amenaza: riesgo intrínseco frente a residual en las cinco dimensiones, en barras superpuestas. Salvaguardas con su peso y un control de madurez L0–L5: al moverlo aparece la barra simulada y la frase «Si op.exp.6 sube a L5, el riesgo medio baja de 3,4 a 2,5 sobre 10. El intrínseco sigue siendo 7,0: la amenaza no desaparece, se contiene». Una salvaguarda con madurez no soportada reduce la mitad. Decisión de tratamiento (reducir, aceptar, transferir, evitar) **sin preselección**: arranca «sin decidir». Aceptar un riesgo alto avisa de que exige firma y queda registrado.

### 10. Componentes y proveedores — `Componentes y proveedores.dc.html`
**Componentes:** cada uno con su vía de cumplimiento de op.pl.5 (CPSTIC, artículo 19 o compensatoria) y el detalle de esa vía, versión, estado de la cualificación y columna «Qué hacer ahora» con la acción que corresponde. «Aportar certificado» y «Renovar ya» abren modal de subida con fechas de emisión y validez y nota para el auditor; las otras dos se resuelven en línea.
**Proveedores:** servicio prestado, certificado ENS con alcance y vigencia, y aviso explícito cuando el alcance no cubre el servicio (por ejemplo, certificado Básica para un sistema Media), con acciones de pedir, subir o registrar hallazgo.

### 11. Documentos — `Documentos.dc.html`
Lista por tipo y estado (vigente, en revisión, borrador, obsoleto) con filtros. Detalle con versiones propias de cada documento, medidas que lo exigen y la acción que toca según el estado. Editor del documento generado con los campos entre llaves que se rellenan del sistema; editar crea un borrador sin tocar la versión vigente. Comparación con la versión anterior (diff línea a línea) solo cuando existe versión con la que comparar.
**Nota técnica:** en el prototipo el editor es un `contentEditable` cuyo contenido se escribe de forma imperativa y se resincroniza al cambiar de documento. En producción, usa el editor del proyecto.

### 12. Incidentes y acciones — `Incidentes y acciones.dc.html`
**Incidentes:** registro con gravedad, responsable y estado; los que lo requieren llevan checks de notificación al CCN-CERT y a la AEPD con su plazo (24 h nivel alto, 72 h AEPD) que al marcarse guardan fecha y autor. La plataforma avisa, no notifica por el cliente.
**Plan de acciones:** hallazgos con su origen (auditoría, incidente, medida, componente), plazo con semáforo, responsable y estado abierta / en curso / hecha. «Vencida» es condición de plazo, no estado de flujo.
**Altas:** modal de registrar incidente (qué ha pasado, gravedad con ayuda contextual, activo afectado, casilla de datos personales que despliega el plazo de la AEPD, adjuntar evidencia) y modal de nueva acción (qué hacer, criterio de cierre, origen, plazo, vínculo).

### 13. Paquete de auditoría — `Paquete de auditoria.dc.html`
Selección de carpetas (el índice `99_Indice` es obligatorio) con recuento de ficheros derivado. **Panel de tarea en segundo plano** con cuatro pasos, progreso, «Puedes seguir trabajando: te avisamos al terminar» y cancelación; al terminar, ZIP con tamaño, número de ficheros y huella SHA-256, más índice en PDF. Si cambia la selección después de generar, el panel pasa a «Paquete desfasado» y el botón a «Regenerar con la selección actual».
**Acceso del auditor:** tabla con persona, empresa auditora y acreditación, correo, alcance concedido, alta, caducidad, último acceso y estado, con revocar (deja traza) o renovar 90 días. Debajo, dos columnas con qué verá y qué no verá el auditor al entrar.
**Antes de entregarlo:** los asuntos que el auditor verá (evidencias caducadas, madurez no soportada, documento sin aprobar, certificado de proveedor corto), cada uno ligado a su carpeta y con enlace a la pantalla donde se arregla. El paquete se genera igualmente: refleja la realidad, no la maquilla.

### 14. Portal del auditor — `Portal del auditor.dc.html`
**Interfaz distinta y minimalista**, sin el resto de la aplicación, con cabecera teal oscura y aviso de acceso de solo lectura con caducidad.
Lista de medidas con filtros y contador de revisadas. Por medida: madurez declarada frente al umbral, tabla de checks `CHK-op.exp.6.x` con resultado editable (sin revisar, conforme, insuficiente, no conforme); los resultados negativos exigen motivo en la propia fila, que se pliega a una línea al guardarse. Los motivos componen la sección de hallazgos, con severidad y plazo. Evidencias con procedencia, fecha, vigencia y estado, que abren un visor lateral superpuesto (vista previa, traza, huella, versiones, checks que cubre, descargar, citar en hallazgo). Herramienta de muestreo con semilla registrada. Marcar como revisada está bloqueado con checks sin resolver o hallazgos sin motivo; existe «revisada con salvedades».

### 15. Panel interno del CPSTIC — `Admin CPSTIC.dc.html`
Interno, cabecera `#0F172A` para que no se confunda con la aplicación del cliente. Subida de la guía CCN-STIC 105 en modal con cotejo automático. Diff del mes en cuatro contadores que filtran (altas, bajas, cambios de versión, dudosas), cada fila con los clientes afectados y qué les ocurre. Las dudosas se resuelven a mano («es el mismo», «es otro producto», «dejar fuera») y bloquean la aprobación. Nada se propaga hasta aprobar; si se cambia una decisión después, avisa de que lo propagado ya no coincide.

### 16. Página pública de confianza — `Pagina publica de confianza.dc.html`
Dos vistas: propietario (con barra de edición e interruptores de qué se publica, que publican de verdad) y visitante. Cabecera teal oscura con categoría y vigencia, datos de certificación, alcance con incluido y excluido, documentación descargable, verificador con número de certificado y, opcional, contacto de seguridad. Nunca se publican el indicador interno, los hallazgos ni el detalle de medidas.

### 17. Móvil — `Movil - evidencias y estado.dc.html`
Las dos únicas cosas que se hacen desde el teléfono (viewport 390 px, objetivos de 44 px mínimo):
- **Subir evidencia:** criterios de «qué debe verse» antes de disparar, hacer foto o galería, vista previa con fecha y ubicación, botón que indica cuántos criterios llevas («Subir igualmente, 1 de 3») con el aviso de que el auditor suele rechazarla.
- **Consultar el estado:** indicador con sus tres componentes y su advertencia, lo que corre prisa y tus tareas con plazo.

### 18. Mapa de navegación — `BLENS.dc.html`
Índice de las pantallas con la barra lateral jerárquica de la navegación real. Es una ayuda de recorrido del prototipo, no una pantalla de producto.

## Interacciones y comportamiento

- **Transiciones:** 160–200 ms, `ease`. Solo cambios de color y de fondo; sin rebotes ni escalas.
- **Modales:** cierre con Escape, con clic en el fondo y con Cancelar. El clic dentro no debe propagarse al fondo.
- **Tablas:** sin scroll horizontal siempre que sea posible; columnas laterales con `white-space: nowrap` y ancho fijo, la columna de texto se queda con el resto. Cuidado con contenidos anchos dentro de una celda: necesitan `min-width: 0` para poder recortarse.
- **Popovers y visores laterales:** superpuestos (`position: absolute` + sombra), nunca robando ancho al contenido.
- **Guardado:** automático y visible; los cambios de estado siempre dejan constancia de fecha y autor.

## Reglas de producto que el diseño refleja

1. **Madurez no soportada:** una medida con madurez declarada pero sin evidencia validada no suma al indicador y se marca en ámbar.
2. **El indicador nunca redondea al alza** y no es una declaración de conformidad.
3. **Sin gamificación:** ni insignias, ni medallas, ni celebraciones. Que suba un número no significa estar conforme.
4. **Un cliente nuevo está a cero por definición:** el estado vacío informa, no alarma.
5. **Estados obligatorios en cada pantalla:** vacío de verdad, cargando, error con salida, caducado (color propio), pendiente de revisión, rechazado con motivo, sugerido por IA (con confianza y origen, nunca confundible con un dato confirmado) y no aplica justificado (visible, no escondido).
6. **Nada de estados atrapados:** si una acción deja algo aprobado, revisado o propagado y después cambia el contenido, la interfaz debe decirlo y permitir deshacer.
7. **Avisos agrupados y accionables**, nunca una notificación por cambio.
8. **Concordancia de número** en todos los contadores («1 evidencia caduca» / «2 evidencias caducan»).

## Estado

- Variables por pantalla: selección actual, filtros, decisiones editadas en línea, estado de modales y de tareas en segundo plano.
- Patrón repetido: el estado de flujo (abierta / revisada / aprobada) se guarda; las condiciones derivadas (vencida, desfasada, bloqueada) se **calculan**, no se almacenan.
- Al accionar varias filas seguidas, usar la forma funcional de actualización de estado para no pisar cambios.

## Vocabulario

Usar: medida · refuerzo · Declaración de Aplicabilidad · categoría (Básica, Media, Alta) · dimensiones (confidencialidad, integridad, disponibilidad, autenticidad, trazabilidad) · evidencia · requisito · check · madurez · paquete de auditoría.

Evitar en la interfaz: «control» (es ISO, no ENS), «compliance», «score», «gap».

Escala de madurez: L0 inexistente · L1 inicial · L2 repetible · L3 definido · L4 gestionado · L5 optimizado. Umbral por categoría: Básica L2, Media L3, Alta L4.

## Assets

No se usa ninguna imagen ni librería de iconos: los indicadores son formas CSS y caracteres (`✓`, `▾`, `▸`, `›`, `–`). Las fuentes se cargan de Google Fonts (Inter y JetBrains Mono). Los espacios de imagen son marcadores; las capturas reales las aporta el cliente.

## Decisiones pendientes

1. Cifras reales de medidas, evidencias y documentos por categoría según el RD 311/2022 (las del prototipo son inventadas).
2. Qué muestra «Ver qué pide el ENS» en la categorización.
3. Si los refuerzos con selección abierta deben ofrecer las alternativas concretas en la Declaración de Aplicabilidad.
4. Estados vacío, de carga y de error en las pantallas distintas del dashboard.
5. Inventario de activos y registro de proveedores como alta, no solo como consulta.

## Ficheros

Todos en `prototipos/`. Cada `.dc.html` se abre directamente en el navegador; `support.js` es el runtime del entorno de prototipado y debe acompañarlos para que se visualicen.

| Fichero | Pantalla |
|---|---|
| `BLENS.dc.html` | Mapa de navegación (empieza por aquí) |
| `Categorizacion.dc.html` | Categorización sin cuenta |
| `Perfilado - Ficha de pregunta.dc.html` | Ficha de pregunta del perfilado |
| `Declaracion de Aplicabilidad.dc.html` | Declaración de Aplicabilidad |
| `Dashboard.dc.html` | Panel principal y estado vacío |
| `Checklist de medidas.dc.html` | Checklist de medidas |
| `Carpeta de evidencias.dc.html` | Carpeta de evidencias |
| `Requisito de evidencia.dc.html` | Detalle de requisito |
| `Activos y dependencias.dc.html` | Grafo de activos |
| `Amenazas y tratamiento.dc.html` | Amenazas, riesgo y simulador |
| `Componentes y proveedores.dc.html` | Componentes y proveedores |
| `Documentos.dc.html` | Documentos |
| `Incidentes y acciones.dc.html` | Incidentes y plan de acciones |
| `Paquete de auditoria.dc.html` | Paquete y acceso del auditor |
| `Portal del auditor.dc.html` | Portal del auditor |
| `Admin CPSTIC.dc.html` | Panel interno del CPSTIC |
| `Pagina publica de confianza.dc.html` | Página pública de confianza |
| `Movil - evidencias y estado.dc.html` | Vistas móviles |

## Capturas

En `capturas/`. Son referencia visual del prototipo, no especificación: ante cualquier duda mandan el texto de este README y el HTML.

| Fichero | Pantalla |
|---|---|
| `00-mapa-navegacion.png` | Mapa de navegación |
| `01-categorizacion.png` | Categorización |
| `02-perfilado.png` | Ficha de pregunta del perfilado |
| `03-declaracion-aplicabilidad.png` | Declaración de Aplicabilidad |
| `01-04-dashboard.png` · `02-04-dashboard.png` | Dashboard con datos y estado vacío |
| `05-checklist-medidas.png` | Checklist de medidas |
| `01-06-carpeta-evidencias.png` · `02-06-carpeta-evidencias.png` | Evidencias: árbol y lista |
| `07-requisito-evidencia.png` | Detalle de requisito |
| `08-activos-dependencias.png` | Grafo de activos |
| `09-amenazas-tratamiento.png` | Amenazas y simulador |
| `01-10-componentes-proveedores.png` · `02-10-componentes-proveedores.png` | Componentes y proveedores |
| `01-11-documentos.png` · `02-11-documentos.png` | Documentos y editor |
| `01-12-incidentes-acciones.png` · `02-12-incidentes-acciones.png` | Incidentes y plan de acciones |
| `13-paquete-auditoria.png` | Paquete y acceso del auditor |
| `14-portal-auditor.png` | Portal del auditor |
| `15-admin-cpstic.png` | Panel interno del CPSTIC |
| `16-pagina-publica.png` | Página pública de confianza |
| `17-movil.png` | Vistas móviles |
