# Evidencias por herramienta — qué acepta un auditor ENS

> Documento compañero de `CLAUDE.md` (M5, M11 y §10bis). Cuando el cliente declara una herramienta en el perfilado, BLENS le dice **qué evidencia subir, con qué opciones alternativas y qué debe verse en ella**. Esta es la especificación de `db/seed/blens/evidence_templates`. **Pendiente de validar medida a medida contra CCN-STIC-808 y con 1-2 auditores ENAC.**

---

## 1. Principio: opciones, no imposiciones

Un auditor no exige un formato concreto: exige **poder comprobar el hecho**. Así que cada requisito se plantea como un **grupo de opciones**: con una vale, y BLENS dice cuál es la más sólida.

```
Requisito: "Demostrar que el antivirus cubre todos los equipos" (op.exp.6)
  Opción A (preferida): export CSV/PDF de la consola con el listado de equipos
  Opción B: captura de pantalla del panel de cobertura
  Opción C: informe del proveedor que gestiona el servicio
  → con una basta; se muestra el orden de preferencia y por qué
```

Jerarquía de solidez, de más a menos:
1. **Export del propio sistema** (CSV, PDF o JSON generado por la herramienta): fechado, íntegro, difícil de discutir.
2. **Captura de pantalla** con contexto visible.
3. **Informe de un tercero** (proveedor, SOC, mantenedor) en su papelería y firmado o sellado.
4. **Declaración del responsable** (acta o certificado interno firmado): solo como complemento, casi nunca como prueba única.

---

## 2. Reglas comunes a toda captura o export

BLENS las muestra una vez, y luego solo recuerda lo específico de cada evidencia:

- **Fecha visible.** La del sistema en la propia imagen o en el export. Si no se ve, vale el export con su metadato de generación.
- **Contexto visible.** Nombre de la consola o URL, y organización o tenant. Una captura recortada que solo muestra un interruptor en verde no prueba de dónde sale.
- **Alcance, no muestra suelta.** Si la medida habla de "todos los equipos", tiene que verse el total y los cubiertos, no un equipo de ejemplo.
- **Del periodo auditado.** Una evidencia de hace tres años no vale para la auditoría de este año.
- **Sin datos personales de más.** Tachar nombres y correos cuando no aportan. Si la evidencia es un listado de usuarios, basta con identificadores.
- **Formato:** PDF o PNG para capturas; CSV o XLSX para listados. BLENS registra quién la subió, cuándo y con qué huella.
- **Muestreo:** cuando el auditor verifica por muestra (altas y bajas, cambios, incidentes), se piden **de 3 a 5 casos del periodo**, no uno.

---

## 3. Catálogo por familia de herramienta

Formato de cada ficha: **medidas** · **evidencia mínima (1 de N)** · **complementarias** · **qué debe verse** · **vigencia** · **qué suele rechazar el auditor**.

### 3.1 Antivirus / EDR
- **Medidas:** op.exp.6 (y op.pl.5 si es componente de seguridad en Media o Alta).
- **Mínima (una):**
  - A. Export del inventario de la consola con estado de protección por equipo.
  - B. Captura del panel de cobertura con totales.
  - C. Informe del proveedor gestionado, fechado y en su papelería.
- **Complementarias:** captura de la política aplicada (análisis programado, protección en tiempo real, acciones ante detección); captura o export de la fecha de última actualización de firmas o motor; export de detecciones del último trimestre con su tratamiento; evidencia de equipos excluidos con justificación.
- **Qué debe verse:** total de equipos frente a equipos protegidos; nombre de la política; fecha; que los servidores también están incluidos.
- **Vigencia:** 3 meses la cobertura; 12 meses la política.
- **Rechazos típicos:** captura de un solo equipo; cobertura del 80 % sin explicar el 20 % restante; la consola muestra equipos "sin comunicar" desde hace meses.
- **Pistas por producto:** *Microsoft Defender for Endpoint* → portal Defender, Activos e Inventario de dispositivos, con exportación. *ESET PROTECT*, *Sophos Central*, *CrowdStrike*, *SentinelOne*, *WithSecure* → panel de dispositivos o Host Management y su informe exportable.

### 3.2 Cortafuegos / perímetro
- **Medidas:** mp.com.1, mp.com.4 (segmentación), op.exp.2 y op.exp.3.
- **Mínima (una):**
  - A. Export de la configuración o del conjunto de reglas.
  - B. Captura de la tabla de reglas con la política por defecto de denegación visible.
  - C. Informe de revisión de reglas del proveedor.
- **Complementarias:** diagrama de red con zonas; acta de la última revisión de reglas con responsable y fecha; captura de la versión de firmware y su soporte vigente; reglas temporales con caducidad.
- **Qué debe verse:** denegación por defecto; reglas con descripción y responsable; zonas separadas (usuarios, servidores, gestión, invitados).
- **Vigencia:** 12 meses la revisión de reglas; el export, del periodo auditado.
- **Rechazos típicos:** reglas "any-any" sin justificar; el diagrama no coincide con las reglas; firmware fuera de soporte.

### 3.3 SIEM / gestión de registros
- **Medidas:** op.exp.8, op.exp.9, op.mon.1 y op.mon.3.
- **Mínima (una):**
  - A. Captura o export de las fuentes integradas con estado de ingesta.
  - B. Informe periódico del SOC con las fuentes cubiertas.
- **Complementarias:** captura de la retención configurada; evidencia de protección de los registros (solo lectura, acceso restringido, integridad); ejemplo de consulta que recupere una acción de administrador del periodo; export de alertas gestionadas.
- **Qué debe verse:** qué sistemas envían registros y cuáles no; plazo de retención; quién puede borrarlos.
- **Vigencia:** 3 meses.
- **Rechazos típicos:** el SIEM solo recoge los cortafuegos y no los servidores ni el directorio; retención inferior a lo declarado en la política; los administradores pueden borrar sus propios registros.

### 3.4 Directorio / identidad y MFA
- **Medidas:** op.acc.1, op.acc.2, op.acc.4, op.acc.5 y op.acc.6.
- **Mínima (una):**
  - A. Export de usuarios con estado, tipo de cuenta y último acceso.
  - B. Captura del panel de usuarios con los totales.
- **Complementarias:** captura de la política de MFA obligatoria y su alcance; export de usuarios con MFA activo frente al total; captura de la política de contraseñas; listado de administradores; evidencia de bloqueo por intentos fallidos; muestra de 3 a 5 altas y bajas con su aprobación; última revisión de permisos firmada.
- **Qué debe verse:** que el MFA es **obligatorio y sin excepciones no justificadas**, no solo "disponible"; cuentas genéricas identificadas y justificadas; que los usuarios de bajas ya no tienen acceso.
- **Vigencia:** 3 meses los listados; 6 o 12 meses la revisión de permisos, según lo declarado.
- **Rechazos típicos:** MFA activado solo para algunos; excepciones permanentes sin justificación; cuentas de personas que ya no están; administradores compartiendo una cuenta.
- **Pistas por producto:** *Entra ID* → Acceso condicional y el informe de métodos de autenticación. *Google Workspace* → Seguridad y Verificación en dos pasos, con informe de usuarios. *Active Directory* → export por PowerShell o GPO de la política de contraseñas.

### 3.5 Gestión de dispositivos (MDM/UEM) y cifrado
- **Medidas:** mp.eq.1, mp.eq.2, mp.eq.3, mp.eq.4, op.exp.2 y op.exp.4.
- **Mínima (una):**
  - A. Export del inventario de dispositivos con estado de cumplimiento.
  - B. Captura del panel de cumplimiento con totales.
- **Complementarias:** informe de cifrado de disco por equipo; captura de la política de bloqueo por inactividad con los minutos; evidencia de borrado remoto disponible; captura de la política de dispositivos personales si se permiten.
- **Qué debe verse:** total frente a cumplidores; cifrado activo en portátiles; minutos de bloqueo coherentes con la normativa interna.
- **Vigencia:** 3 meses.
- **Rechazos típicos:** cifrado "configurado" pero con equipos sin cifrar en el informe; bloqueo a 60 minutos cuando la norma dice 10.

### 3.6 Copias de seguridad
- **Medidas:** mp.info.6, op.cont.3 (si Disponibilidad es Alta) y mp.si.2.
- **Mínima (una):**
  - A. Export o captura de los trabajos de copia con su calendario y resultado.
  - B. Informe periódico del proveedor de copias.
- **Complementarias:** **acta de prueba de restauración** con fecha, alcance y resultado; captura del cifrado de las copias; evidencia de copia fuera de sitio o inmutable; captura de la retención; export de fallos y su tratamiento.
- **Qué debe verse:** qué sistemas se copian y con qué frecuencia; que las copias **terminan bien** (no solo que están programadas); una restauración probada de verdad.
- **Vigencia:** 3 meses el registro de ejecuciones; 12 meses la prueba de restauración.
- **Rechazos típicos:** no hay prueba de restauración, solo copias; la prueba es de hace tres años; se copia el servidor pero no la base de datos; copias en la misma máquina.
- **Pistas por producto:** *Veeam* → informes de trabajos y SureBackup. *Azure Backup* / *AWS Backup* → panel de trabajos y políticas. *Microsoft 365* → nota de auditor: la papelera y la retención nativa no son copia de seguridad.

### 3.7 Parcheo y vulnerabilidades
- **Medidas:** op.exp.4 y op.exp.5.
- **Mínima (una):**
  - A. Informe de cumplimiento de parches por equipo.
  - B. Captura del panel con el porcentaje al día y los pendientes.
- **Complementarias:** último informe de escaneo de vulnerabilidades con su plan de remediación; procedimiento con plazos por criticidad; muestra de 3 cambios con aprobación y prueba; excepciones con justificación y caducidad.
- **Qué debe verse:** plazos reales frente a los comprometidos; equipos con parches críticos pendientes y por qué.
- **Vigencia:** 1 mes el estado de parches; 3 o 12 meses el escaneo según lo declarado.
- **Rechazos típicos:** "se actualiza automáticamente" sin informe; vulnerabilidades críticas abiertas desde hace meses sin justificación.

### 3.8 Correo electrónico
- **Medidas:** mp.s.1 y mp.per.3 (si hay simulaciones de phishing).
- **Mínima (una):**
  - A. Captura de las políticas antispam, antimalware y antiphishing activas.
  - B. Informe del servicio de protección de correo.
- **Complementarias:** **registros DNS SPF, DKIM y DMARC** (captura de la zona o de una herramienta de comprobación); captura de la política de cifrado en tránsito; resultados de la última simulación de phishing.
- **Qué debe verse:** política aplicada a todo el dominio; DMARC en cuarentena o rechazo, no solo en "none".
- **Vigencia:** 12 meses.
- **Rechazos típicos:** SPF sin DKIM ni DMARC; DMARC en modo monitorización presentado como protección.

### 3.9 Web, sede electrónica y WAF
- **Medidas:** mp.s.2, mp.com.2 y mp.com.3.
- **Mínima (una):**
  - A. Informe de test de intrusión o de análisis de vulnerabilidades web.
  - B. Captura de la configuración del WAF con el modo de bloqueo activo.
- **Complementarias:** informe de configuración TLS (versiones y cifradores); certificados con su caducidad; plan de remediación de los hallazgos; evidencia de cabeceras de seguridad.
- **Qué debe verse:** alcance del análisis (qué URL); fecha; hallazgos con su estado; que el WAF bloquea y no solo observa.
- **Vigencia:** 12 meses el análisis; continua la configuración.
- **Rechazos típicos:** informe de hace dos años; hallazgos altos sin remediar ni justificar; WAF en modo detección.

### 3.10 Acceso remoto (VPN) y navegación
- **Medidas:** op.acc.6, mp.com.2 y mp.s.3.
- **Mínima (una):**
  - A. Captura de la configuración de la VPN con cifrado y MFA.
  - B. Export de conexiones del periodo.
- **Complementarias:** listado de usuarios con acceso remoto; captura del filtrado de navegación o DNS seguro; política de teletrabajo firmada.
- **Qué debe verse:** MFA exigido también en remoto; algoritmos y versiones aceptables; quién tiene acceso.
- **Vigencia:** 3 meses.
- **Rechazos típicos:** VPN sin segundo factor; protocolos obsoletos.

### 3.11 Cuentas privilegiadas (PAM) y claves
- **Medidas:** op.acc.2, op.acc.3, op.acc.6 y op.exp.10.
- **Mínima (una):**
  - A. Export de cuentas privilegiadas con su propietario.
  - B. Captura del panel de la bóveda o del PAM.
- **Complementarias:** evidencia de grabación o registro de sesiones; procedimiento del ciclo de vida de claves y certificados; inventario de certificados con caducidad; captura del HSM o del servicio de claves; evidencia de rotación.
- **Qué debe verse:** cuántos administradores hay y quiénes; que las credenciales no están en hojas de cálculo ni en el código; custodia de las claves.
- **Vigencia:** 6 meses.
- **Rechazos típicos:** contraseñas de administración en un Excel compartido; claves en repositorios; nadie sabe cuándo caducan los certificados.

### 3.12 Instalaciones y CPD propio (no es software, pero se pregunta igual)
- **Medidas:** mp.if.1 a mp.if.7.
- **Mínima (varias, según la medida):** fotos del control de acceso y de la sala; plano o croquis; extracto del registro de accesos; contratos y partes de mantenimiento de climatización, SAI y extinción; certificado de la instalación de incendios con su última revisión; informe de prueba del SAI o del grupo; registro de entradas y salidas de equipamiento.
- **Qué debe verse:** que la sala está separada y con acceso restringido; que los mantenimientos están al día y hechos por empresa autorizada; fechas.
- **Vigencia:** la del mantenimiento correspondiente, normalmente 12 meses.
- **Rechazos típicos:** fotos sin fecha ni contexto; extintores caducados; el registro de accesos existe pero está vacío.

### 3.13 Concienciación y formación
- **Medidas:** mp.per.2, mp.per.3 y mp.per.4.
- **Mínima (una):**
  - A. Registro de la plataforma de formación con participantes y fecha.
  - B. Email de convocatoria más lista de asistencia firmada.
- **Complementarias:** material impartido; evaluación o certificados; resultados de la simulación de phishing; acuse de lectura de la normativa; plan anual de formación.
- **Qué debe verse:** **cobertura**, es decir, cuántas personas de la plantilla han participado; fecha dentro del periodo; que los nuevos también han pasado por ahí.
- **Vigencia:** 12 meses.
- **Rechazos típicos:** una charla a la que fueron 10 de 80 personas; convocatoria sin prueba de asistencia; no hay nada para las incorporaciones del año.
- **Nota:** con M12, BLENS **genera esta evidencia por sí solo** (convocatoria, asistencia y acuse dentro de la plataforma).

### 3.14 Incidentes y continuidad
- **Medidas:** op.exp.7, op.exp.9, op.cont.1 a op.cont.4.
- **Mínima (una):**
  - A. Export del registro de incidentes del periodo.
  - B. Informe del SOC o del proveedor con los incidentes gestionados.
- **Complementarias:** procedimiento aprobado; ejemplo completo de un incidente con su cronología y cierre; evidencia de notificación externa si hubo; informe de la última prueba del plan de continuidad; contratos de medios alternativos.
- **Qué debe verse:** que el registro se usa de verdad (no está vacío); tiempos de detección y resolución; lecciones aprendidas.
- **Vigencia:** continua el registro; 12 meses la prueba de continuidad.
- **Rechazos típicos:** "no hemos tenido incidentes" con un registro que no existe; plan de continuidad sin probar nunca.

### 3.15 Nube y SaaS
- **Medidas:** op.nub.1, op.ext.1, op.ext.2 y op.exp.2.
- **Mínima (una):**
  - A. Export de configuración o informe de postura de seguridad de la plataforma.
  - B. Capturas de los puntos clave: MFA de administración, registro de auditoría activado, cifrado y región de los datos.
- **Complementarias:** **certificado de conformidad ENS del proveedor** con su alcance y vigencia; matriz de responsabilidad compartida; contrato y acuerdos de nivel de servicio; informes periódicos del servicio; encargo de tratamiento si hay datos personales.
- **Qué debe verse:** que la categoría del certificado del proveedor es **igual o superior** a la del sistema; región dentro de la UE si así se ha declarado; quién configura qué.
- **Vigencia:** la del certificado; 3 meses el informe de postura.
- **Rechazos típicos:** confundir ISO 27001 del proveedor con conformidad ENS; certificado caducado; alcance del certificado que no cubre el servicio contratado.

### 3.16 Herramientas con implicación CPSTIC (op.pl.5, Media y Alta)
Además de la evidencia funcional de su familia, cada componente de seguridad aporta la de su **ruta** (ver `CLAUDE.md` §3.2):
- **Ruta CPSTIC:** ficha del catálogo fechada, captura de la versión instalada coincidente con la cualificada, y evidencia de configuración según su Procedimiento de Empleo Seguro.
- **Ruta certificado del artículo 19:** certificado con su alcance, y consulta fechada que demuestre que no hay alternativa cualificada para esa funcionalidad.
- **Ruta compensatoria:** justificación, riesgo asociado, medidas compensatorias y plan de sustitución con fecha.
- **Qué suele rechazar el auditor:** versión instalada distinta de la cualificada; "elegimos otra marca porque nos gustaba más" como justificación.

---

## 4. Implicaciones para el modelo y la UI

1. **Grupos de opciones.** `EvidenceTemplate` necesita un `option_group`: varias plantillas alternativas satisfacen un mismo requisito y basta una. La UI muestra la preferida primero y las demás como "también vale".
2. **Criterios de aceptación explícitos.** Cada plantilla lleva una lista de comprobaciones ("se ve la fecha", "se ve el total de equipos"). El cliente las marca al subir, y el revisor las usa para validar o rechazar con motivo concreto.
3. **Pistas por producto.** Una tabla de sugerencias por producto conocido (dónde encontrarlo en Defender, Entra, Veeam, Fortinet…) que se aplica cuando el perfilado identifica el producto. Es contenido curado, ampliable sin tocar código.
4. **Vigencia por evidencia**, no por medida: la cobertura del antivirus caduca en 3 meses, su política en 12.
5. **Rechazos típicos como ayuda preventiva.** Se muestran antes de subir, en la línea de "el auditor rechazará esto si…". Evita una ronda de correcciones.
6. **Reutilización.** Una captura de MFA sirve para op.acc.6 y op.nub.1: se sube una vez y se enlaza a todos los requisitos que cubre.

---

## 5. Pendientes

- [ ] Validar cada ficha contra la CCN-STIC-808 y **con 1-2 auditores ENAC en ejercicio**. Los "rechazos típicos" son la parte más valiosa y la que más conviene contrastar.
- [ ] Redactar ejemplos anonimizados de cada evidencia (capturas modelo).
- [ ] Ampliar las pistas por producto empezando por los más comunes en la Administración española.
- [ ] Revisar la coherencia con el CPSTIC: las familias de este catálogo deberían casar con las familias de producto de la CCN-STIC-140.
