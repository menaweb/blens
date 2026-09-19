# Ingesta asistida por IA — diseño

> Documento compañero de `CLAUDE.md` (M16). Equivalente al agente de ingesta de Vanta, adaptado al ENS. **Regla que no se negocia: la IA propone, una persona confirma.** Nada que proponga la IA entra en el cálculo ni en el paquete de auditoría sin revisión humana registrada.

---

## 1. Por qué merece la pena

El cliente que llega a BLENS casi nunca llega vacío: tiene una política de 2019 en Word, un Excel de controles, un informe de auditoría anterior con no conformidades, un análisis de riesgos hecho con PILAR y una carpeta compartida con 200 ficheros. Hoy eso se transcribe a mano, y es la barrera real de adopción.

Con ingesta asistida, el cliente **arrastra lo que ya tiene** y BLENS le devuelve un punto de partida: qué medidas están cubiertas, qué documentos sirven y qué falta.

---

## 2. Casos de uso, por retorno

| # | Caso | Entrada | Salida (propuesta) | Valor |
|---|---|---|---|---|
| 1 | **Importar la DdA o el Excel de controles previo** | XLSX, DOCX, PDF | `MeasureAssessment` con madurez y responsable por medida, medidas no aplicables con su justificación | Ahorra la carga inicial completa; imprescindible en renovaciones |
| 2 | **Importar el informe de auditoría anterior** | PDF | Hallazgos y no conformidades → PAC (M13) con medida afectada | Convierte el informe en plan de trabajo |
| 3 | **Clasificar una carpeta entera de documentos** | ZIP o carga múltiple | Por fichero: tipo de documento, fecha, versión, medidas y requisitos que cubre | Rellena la carpeta de evidencias de golpe |
| 4 | **Emparejar lo existente con los requisitos y detectar huecos** | Lo anterior + perfilado | Requisitos cubiertos, cubiertos parcialmente y vacíos | Es el "qué me falta" con el que arranca el proyecto |
| 5 | **Detectar contradicciones documentales** | Documentos + respuestas del perfilado | Avisos de incoherencia | Ver §3, es el diferenciador |
| 6 | **Revisar la calidad de una evidencia** | Captura o export subido | Comprobación contra los criterios de aceptación de la plantilla | Evita la ronda de correcciones |
| 7 | **Rellenar variables de plantillas** (M3) | Documentos previos | Nombres de roles, órganos, alcance, plazos | Documentación generada con su vocabulario, no genérica |
| 8 | **Importar un análisis de riesgos PILAR** | Informe o export | Activos, dependencias y valoraciones para M7 | Aprovecha el trabajo ya pagado |
| 9 | **Redactar textos operativos** | Contexto del caso | Email al proveedor pidiendo su certificado, justificación de no aplicabilidad, explicación de un hallazgo en lenguaje llano | Quita fricción en lo tedioso |

---

## 3. Detección de contradicciones (el diferenciador)

Un auditor encuentra incoherencias comparando lo que dice el papel con lo que muestra el sistema. BLENS puede hacerlo antes, porque tiene las dos cosas en el mismo sitio:

- La normativa dice bloqueo de pantalla a los 10 minutos; la captura del MDM muestra 60.
- La política de copias dice diarias con retención de 30 días; el informe de trabajos muestra semanales.
- La DdA excluye una medida por "no hay desarrollo propio", pero el perfilado declara desarrollo interno.
- El documento de alcance no incluye un sistema que sí aparece en el inventario.
- La política nombra un Responsable de Seguridad que ya no está en la organización.
- El análisis de riesgos trata una amenaza sobre un activo que ya no existe.

Cada aviso señala las dos fuentes enfrentadas y propone cuál actualizar. **Nunca decide por su cuenta.**

---

## 4. Reglas de diseño (obligatorias)

1. **La IA solo propone datos de tenant.** Nunca escribe en el catálogo ENS, nunca en `CpsticEntry`, y **nunca entra en los motores**: `risk_engine` y `scoring_engine` siguen siendo deterministas y solo consumen datos confirmados.
2. **Todo lo propuesto nace en estado `SUGERIDO`**, con `origen = IA`, nivel de confianza y **cita de origen** (fichero, página y párrafo o celda). Una persona lo acepta, lo corrige o lo rechaza, y eso queda en traza inmutable: ante el auditor hay que poder decir quién decidió cada dato.
3. **Nada sugerido cuenta para el indicador de listo para auditoría** hasta que se confirma. Si no, se fabrica la falsa sensación de cumplimiento que critican los usuarios de las plataformas automatizadas.
4. **Revisión por lotes.** La UI muestra las sugerencias agrupadas (por medida o por documento) con aceptar todo o revisar una a una, y el porcentaje de confianza visible. Aceptar en bloque exige confirmación explícita.
5. **Los documentos del cliente son datos, no instrucciones.** Extracción con esquema estructurado y salida validada contra él. Si un documento contiene texto que parece una orden, se ignora. Esto se prueba con casos de inyección en la suite de tests.
6. **Umbral de confianza.** Por debajo del umbral configurado, no se sugiere: se deja el requisito como pendiente. Más vale un hueco honesto que una propuesta que nadie revisa.
7. **La comprobación visual de evidencias es complemento, no sustituto.** Sirve para avisar ("no se ve la fecha", "no se ve el total de equipos"), no para validar. La validación es siempre humana.
8. **Todo opcional y desactivable por tenant.** Un organismo puede decidir no enviar sus documentos a un modelo, y BLENS debe funcionar igual sin esta función.

---

## 5. Privacidad y arquitectura

Aquí está el riesgo real del producto: BLENS aspira a ENS Alto y sus clientes son sector público.

- **Proveedor del modelo = subencargado.** Hay que declararlo en la lista de subprocesadores, en el contrato de encargo de tratamiento y en el registro de actividades de tratamiento. Es un argumento de venta o un problema, según cómo se resuelva.
- **Residencia y retención.** Opción por defecto: **Amazon Bedrock en la misma región del despliegue** (eu-south-2 o eu-west-1), con retención cero y sin uso de los datos para entrenamiento. Alternativa para clientes que lo exijan: modelo autoalojado en la propia cuenta, con menor calidad y más coste.
- **Minimización.** Se envía el fragmento necesario, no el documento entero cuando se puede evitar; se tachan datos personales irrelevantes antes de enviar.
- **Cuota y coste** por tenant, con el trabajo pesado en Celery. La ingesta de una carpeta es una tarea, nunca una petición web.
- **Trazabilidad técnica:** qué modelo y versión, qué fragmento se envió y qué devolvió, para poder explicar una sugerencia meses después.

---

## 6. Cómo se mide

- **Tasa de aceptación** de sugerencias por caso de uso. Por debajo del 70 %, el caso de uso no está listo y se desactiva.
- **Tiempo hasta el primer paquete completo** frente a clientes sin ingesta.
- **Falsos positivos en contradicciones**: un aviso equivocado quema la confianza más rápido que la ausencia de aviso.
- **Correcciones posteriores:** cuántos datos aceptados se corrigen después. Indica confianza excesiva del revisor.

---

## 7. Fases

| Fase | Contenido |
|---|---|
| **Primera (post-v1, alto retorno y bajo riesgo)** | Casos 1, 2 y 3: importar DdA previa, informe de auditoría y clasificar documentos. Entrada estructurada, salida revisada. |
| **Segunda** | Casos 4 y 5: emparejamiento con requisitos, huecos y contradicciones. |
| **Tercera** | Casos 6, 7, 8 y 9: comprobación visual de evidencias, variables de plantillas, importación de PILAR y redacción de textos. |

No entra en la v1: la v1 tiene que sostenerse sin IA. Si el producto solo funciona con el asistente, el asistente es el producto y el motor no vale nada.

---

## 8. Pendientes

- [ ] Decidir proveedor y modelo, y firmar el acuerdo de encargo con retención cero.
- [ ] Redactar la lista de subprocesadores y el texto para el comprador público, que preguntará.
- [ ] Preparar un conjunto de prueba con documentación ENS real y anonimizada para medir la tasa de aceptación antes de lanzar.
- [ ] Casos de inyección de instrucciones en los tests desde el primer día.
- [ ] Definir el umbral de confianza por caso de uso, con datos, no a ojo.
