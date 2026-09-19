# Competencia, UX y requisitos derivados — BLENS

> Documento compañero de `CLAUDE.md`. Traduce la investigación de mercado (septiembre 2026) en **requisitos implementables**. Cada patrón lleva el módulo donde se implementa. Los datos de terceros son orientativos: los precios de las GRC internacionales son estimaciones porque no publican tarifa, y varias cifras provienen del marketing del propio fabricante.

---

## 1. Mapa competitivo

Tres mundos que nadie ha unido bien, y ahí está el hueco de BLENS:

| Mundo | Quién | Fuerte | Débil |
|---|---|---|---|
| **Oficial del CCN** (gratis, canónico para el auditor) | PILAR (riesgos MAGERIT), AMPARO (adecuación y DdA), INES (reporte anual), CLARA (bastionado), LUCIA (incidentes) | Metodología completa y aceptada sin fricción por el auditor | UX anticuada, herramientas desconectadas entre sí, sin colaboración |
| **GRC española de empresa** | GlobalSuite, ISOTools/GRCTools, SandaS (Govertis/Telefónica Tech) | Multimarco, BI, trazabilidad | Precio no público, venta por demo, curva de aprendizaje, informes flojos |
| **GRC internacional de automatización** | Vanta, Drata, Secureframe, Sprinto, Hyperproof; open source Eramba, SimpleRisk, CISO Assistant | UX excelente, onboarding guiado, portal de auditor, trust center, recogida automática de evidencias | No entienden ENS ni MAGERIT |

**Competidor directo más serio: Formalize** (danesa). Ya tiene módulo ENS + MAGERIT + NIS2 con catálogos MAGERIT precargados, cálculo de impacto por dimensiones, recálculo y propagación en tiempo real a servicios y proveedores, DdA automática con trazabilidad riesgo→control, contenido preconfigurado y reutilización de evidencias entre ENS y NIS2. Tiene prueba gratuita, ISO 27001 e ISAE 3000. Confirma que la tesis de BLENS es válida; hay que ejecutarla **más española**: auditor ENAC, CPSTIC, checks CCN-STIC-808.

**Referencia de self-serve español: Cumpleo** (4DLegal). Cuestionario gratuito de tres minutos sin registro, autogeneración documental versionada, avisos de cambio normativo y **precio público muy bajo** (del orden de 25 € el primer año). Su gancho es exactamente el de BLENS (M1 gratis) pero sin motor MAGERIT propio.

---

## 2. Qué copiar, y dónde se implementa

| # | Patrón | Origen | Módulo BLENS | Requisito concreto |
|---|---|---|---|---|
| 1 | Onboarding por cuestionario adaptativo que **autogenera documentación** | Cumpleo, Vanta | M1 + M11 + M3 | Al terminar el perfilado: borrador de DdA y plan de adecuación, sin pasos manuales |
| 2 | **DdA automática también en MEDIA y ALTA** | AMPARO solo la genera en BÁSICA | M2 | Diferenciador directo frente a la herramienta oficial; exige resolver refuerzos y selecciones |
| 3 | **"% listo para auditoría"** con semáforo por medida y por marco | Vanta, Drata, AMPARO | M6 | Ver §3: definición del indicador |
| 4 | **Caducidad y renovación de evidencias** con recordatorios | Eramba, Drata | M5 | Ya en el modelo (`vigencia_dias`); añadir aviso previo configurable y panel de "caduca pronto" |
| 5 | **Portal del auditor** de solo lectura con muestreo y peticiones | Drata Audit Portal | M14 (nuevo) | Ver §4 |
| 6 | **Procedencia y sello de tiempo** en cada evidencia | Drata | M5 + M8 | Quién la subió, cuándo, de qué sistema, hash; visible en el índice |
| 7 | **Acoplamiento riesgo↔cumplimiento con recálculo inmediato** y propagación a proveedores | Formalize, SimpleRisk | M7 | Al cambiar una madurez, el riesgo residual se actualiza y se ve el delta |
| 8 | **Mapeo de una evidencia a varios marcos** (ENS ↔ ISO 27001 ↔ NIS2) | Eramba, Vanta, Formalize | F6 | Modelo `ControlMapping`; subir una vez, enlazar a varios requisitos |
| 9 | **Acuse de lectura de políticas** y alta/baja de empleados | Vanta, Eramba | M12 | Ya incorporado |
| 10 | **Portal de confianza público** | SafeBase (comprado por Drata en 2025), Vanta | M15 (post-v1) | Página pública con el estado ENS del proveedor, útil en licitaciones |
| 11 | **Vistas cruzadas riesgo↔activo↔control** | SimpleRisk | M6 + M7 | "Qué activos concentran riesgo" y "qué riesgos afectan a más activos" |
| 12 | **Excepciones con propietario, justificación y caducidad** | Eramba, SimpleRisk | M2 + M13 | Una no-aplicabilidad o una compensatoria caduca y se revisa |
| 13 | **Precio público** y renovación garantizada | Cumpleo (a favor), Vanta y Drata (en contra) | Producto | Ver §6 |

---

## 3. Indicador "listo para auditoría" (M6)

Define un solo número que el cliente y su dirección entiendan. Se calcula con `scoring_engine` y **no se inventa**: es la media ponderada de tres componentes, cada uno visible por separado.

1. **Madurez suficiente:** medidas aplicables cuyo nivel alcanza el umbral de su categoría (Básica L2, Media L3, Alta L4).
2. **Evidencia viva:** requisitos obligatorios con evidencia **validada y no caducada**.
3. **Documentación vigente:** documentos obligatorios en estado `VIGENTE` (M8).

Reglas:
- Una medida con madurez declarada pero sin evidencia validada cuenta como **"madurez no soportada"** y no suma. Es lo primero que detecta un auditor.
- El indicador nunca se redondea al alza.
- Se muestra el desglose por marco y familia, el ranking de gaps y el delta desde la última semana.
- **Sin gamificación.** Que el número suba no significa estar conforme: la conformidad la declara el auditor. El panel lo dice de forma explícita.

---

## 4. M14 · Portal del auditor (v1)

Inspirado en el portal de auditor de Drata, pero para el flujo ENAC:

- Acceso por invitación con caducidad, **solo lectura**, sin necesidad de cuenta de pago.
- El auditor ve lo mismo que el cliente: medidas, checks 808, evidencias con su fecha y procedencia, y documentos vigentes.
- **Muestreo:** el auditor fija el tamaño de muestra y el sistema le propone los elementos (tickets de alta y baja, cambios, incidentes); puede ajustarla y queda registrada.
- **Peticiones de información:** el auditor abre una petición, se asigna a un responsable del cliente y se cierra con la evidencia aportada. Sustituye el correo de ida y vuelta.
- **Marcado de revisado** por medida, con hallazgos que caen al PAC (M13).
- Todo lo que hace el auditor queda en traza inmutable.
- Enlaces a S3 firmados y con caducidad; nunca acceso directo al bucket.

---

## 5. Antipatrones y requisitos que obligan

De la crítica documentada de PILAR (TFG de la Universidad de Valladolid, revisado por el creador de la herramienta, que reconoce que los menús no son muy funcionales) y de las reseñas de las GRC comerciales:

| Antipatrón observado | Requisito que asumimos |
|---|---|
| Sobrecarga de opciones; el modo "básico" apenas cambia el menú | **Divulgación progresiva real**: por defecto simple; el modo experto añade opciones, no las revela todas de golpe |
| Etiquetas crípticas e inconsistentes | Glosario en línea y una sola voz en toda la UI (ver §1bis del cuestionario) |
| Grafo de dependencias rígido: no se mueven varios nodos, el % no se ve en las aristas, scroll lento | El editor de dependencias (M7) exige: **multiselección**, **% visible en la arista**, zoom fluido, ajuste automático y detección de ciclos con mensaje claro |
| Sin deshacer; valoración a base de doble clic y desplegable | **Ctrl+Z en toda la app** y entrada de valoraciones **tipo hoja de cálculo** (teclado, tabulador, pegar desde Excel) |
| Instalación por máquina, sin multiusuario simultáneo | SaaS colaborativo: varios usuarios a la vez, bloqueo por sección y traza de quién cambió qué |
| Informes pobres (queja recurrente de GlobalSuite) | La calidad del paquete de auditoría (M9) es criterio de aceptación, no un extra |
| "Falsa sensación de cumplimiento" del checkbox automático | Separar **declarado** de **demostrado**; la madurez sin evidencia no cuenta (§3) |
| Precio opaco y subidas de renovación agresivas | Precio público y renovación garantizada (§6) |
| Alertas ruidosas | Avisos agrupados y accionables; nada de notificar por notificar |

---

## 6. Precio y posicionamiento (decisión de producto pendiente)

Referencias del mercado:
- **Herramientas del CCN:** gratuitas. Compiten en coste cero, no en experiencia.
- **Cumpleo:** decenas de euros al año, autoservicio total.
- **Packs de consultoría con software en España:** del orden de 3.000 € el primer año en Básica y 8.000 € en Media/Alta, con la auditoría ENAC aparte.
- **GRC internacionales:** entre 6.000 y 25.000 € al año, sin precio público y con renovaciones al alza.
- **GRC españolas de empresa:** proyecto, sin tarifa pública.

Posición propuesta: **precio público, autoservicio, entre Cumpleo y los packs de consultoría**, con la categorización gratuita como gancho y la renovación garantizada como argumento explícito frente a la queja número uno de las plataformas internacionales. Pendiente de validar con dos o tres clientes reales.

---

## 7. Huecos de mercado (lo que nadie hace bien)

1. **Paquete de evidencias maquetado para el auditor ENAC**, alineado con CCN-STIC 802 (auditoría), 808 (verificación) y 809 (declaración y certificación de conformidad).
2. **Riesgo vivo acoplado al cumplimiento.** Hoy PILAR y AMPARO están desconectados y el análisis de riesgos acaba siendo un documento muerto.
3. **DdA automática en MEDIA y ALTA**, que AMPARO no genera.
4. **Integración con CPSTIC** para avisar de productos no cualificados o con la cualificación caducada.
5. **Checks técnicos** en el mismo panel (hoy CLARA va por separado).
6. **Autoservicio con precio público** para las pymes proveedoras de la Administración.

---

## 8. Para revisar con calma

- PILAR: `pilar.ccn-cert.cni.es`; crítica de usabilidad con capturas: TFG de la UVa (`uvadoc.uva.es`, TFG-G4133).
- AMPARO: documentación de caso de uso en `ccn-cert.cni.es` (pantallas del asistente y gestión de la conformidad).
- Portal del auditor de Drata: `help.drata.com`, artículos sobre el Audit Portal y lo que ve el auditor.
- Formalize ENS/MAGERIT: `formalize.com/es/esquema-nacional-de-seguridad-ens-magerit-nis2`.
- Cumpleo: `cumpleo.com` (servicios ENS y tarifas).
- GlobalSuite ENS y sus reseñas en Capterra y G2.
- Eramba (`eramba.org/learning`) y SimpleRisk (`simplerisk.com`) para patrones de excepciones, acuses y vistas cruzadas.
- Catálogo CPSTIC, apartado de conformidad y gobernanza: `cpstic.ccn.cni.es`.

---

## 9. Pendientes que salen de la investigación

- [ ] **Verificar la marca "BLENS".** Existe "BL España Software / Berger-Levrault", con certificado ENS de categoría ALTA. No es competidor directo, pero conviene comprobar riesgo de confusión y disponibilidad de marca y dominio.
- [ ] Probar en persona AMPARO y PILAR para copiar su vocabulario exacto: es el que usará el auditor.
- [ ] Conseguir el crosswalk ENS↔ISO 27001 (CCN-STIC-825 u otra equivalencia publicada) y decidir si se compra o se construye.
- [ ] Confirmar el estado de la transposición española de NIS2 antes de mencionarla en el producto.
- [ ] Hablar con una o dos entidades certificadoras acreditadas por ENAC: qué formato de paquete les ahorra tiempo de verdad (valida M9 y M14).
