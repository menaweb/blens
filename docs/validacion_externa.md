# Validación externa — guion de trabajo

> Documento compañero de `CLAUDE.md`. Todo lo construido hasta ahora está hecho con criterio, pero **sin contrastar con nadie**. Este documento prepara las tres conversaciones que lo validan: un auditor ENAC, una entidad de certificación y un cliente piloto. El objetivo no es enseñar el producto: es que te digan dónde te equivocas antes de escribir el código.

**Cuándo:** antes de terminar F4 (perfilado y evidencias). Después es rehacer.

---

## 1. Sesión con un auditor ENAC en ejercicio

**A quién buscar:** alguien que audite ENS habitualmente, no un consultor de implantación. Los dos papeles ven cosas distintas y el que decide es el auditor. Si puede ser, dos perfiles: uno de una certificadora grande y otro de una pequeña, porque su nivel de exigencia práctica difiere.

**Qué ofrecer a cambio:** acceso gratuito al producto cuando esté, o pago por la sesión. Pagar una o dos horas de consultoría sale barato comparado con construir tres meses en la dirección equivocada.

**Qué llevar:**
- `docs/evidencias_por_herramienta.md` impreso, sobre todo los **rechazos típicos**.
- Un extracto de 10 a 15 checks de `checks.op_exp.yaml` con su método de verificación.
- El árbol de carpetas del paquete (§10 de `CLAUDE.md`).
- La ficha previa para la certificadora (§7 de `docs/cuestionario_perfilado.md`).

**Guion (60–90 minutos):**

1. **Cómo trabaja de verdad.** Antes de enseñar nada:
   - ¿Cómo le llega hoy la documentación del cliente? ¿Carpeta compartida, correo, papel?
   - ¿Cuánto tiempo pierde persiguiendo evidencias que faltan o no sirven?
   - ¿Qué le hace pensar, en la primera hora, que esta auditoría va a ir mal?
   - ¿Qué formato le ahorraría más tiempo? (Escuchar sin sugerir: es la pregunta más valiosa del día.)
2. **Los rechazos típicos, uno a uno.** Leerle diez y preguntar: ¿esto lo rechazarías? ¿Qué pedirías en su lugar? Marcar los que confirme, los que matice y los que le parezcan excesivos.
3. **Muestreo.** ¿Cuántos casos coge de altas y bajas, de cambios, de incidentes? ¿Cómo elige la muestra? ¿Aceptaría que el sistema se la propusiera, o quiere elegirla él?
4. **Vigencia.** ¿Cuánto tiempo acepta que tenga una evidencia? ¿Distingue por tipo? Contrastar con los `vigencia_dias` del seed.
5. **Madurez sin evidencia.** Presentarle el concepto de "madurez no soportada": ¿es útil o es ruido?
6. **El paquete.** Enseñar el árbol de carpetas: ¿le sirve tal cual? ¿Qué le sobra, qué le falta, en qué orden lo quiere?
7. **El portal del auditor.** Describir M14 sin enseñar pantallas: acceso de solo lectura, muestreo, peticiones. ¿Lo usaría o preferiría descargar el ZIP y trabajar aparte? **Si dice que prefiere el ZIP, eso cambia la prioridad de M14.**
8. **La pregunta final:** si un cliente llegara con esto preparado, ¿cuánto tiempo de auditoría se ahorraría? Esa cifra es vuestro argumento comercial, dicha por quien audita.

**Qué hacer con lo que salga:** cada rechazo confirmado o corregido se actualiza en `evidence_templates.*.yaml`. Anotar en el propio fichero quién lo validó y cuándo.

---

## 2. Sesión con una entidad de certificación (oficina técnica)

**A quién:** cualquiera de las acreditadas por ENAC para certificar el ENS. Basta con pedir presupuesto ficticio para un caso tipo: se ve qué piden antes de dar precio.

**Objetivo:** validar la ficha previa (§7 de `docs/cuestionario_perfilado.md`) y entender su proceso.

**Guion (45 minutos):**
1. ¿Qué información pedís antes de hacer una oferta? Pedir el formulario real.
2. ¿Qué datos determinan los días de auditoría? (No para calcularlos nosotros, sino para saber qué recoger.)
3. ¿Qué os hace descartar o retrasar un proyecto?
4. ¿Cómo entregáis el plan de auditoría al cliente? ¿En qué formato?
5. ¿Cómo os gustaría recibir las evidencias?
6. ¿Aceptaríais un acceso de solo lectura a una herramienta del cliente, o preferís ficheros?
7. ¿Tenéis interés en que vuestros clientes lleguen preparados con una herramienta así? (Aquí se ve si hay canal de venta: las certificadoras no pueden consultar al cliente que auditan, pero sí recomendarle herramientas.)

**Ojo con el conflicto de interés:** una certificadora no puede asesorar a quien audita. Plantearlo como recomendación genérica a sus clientes, nunca como colaboración en la implantación.

---

## 3. Cliente piloto

**A quién:** dos perfiles distintos, porque los caminos del cuestionario son muy diferentes:
- Una **pyme proveedora** de la Administración, categoría Básica, todo en la nube.
- Un **organismo pequeño** (ayuntamiento, consorcio, fundación pública), categoría Media, con CPD propio.

**Qué pedirles:** dos horas y su documentación real. A cambio, uso gratuito hasta la primera auditoría.

**Protocolo de la sesión (90 minutos, sin ayudar):**
1. Se les pasa el cuestionario **sin explicarlo**, con la instrucción de pensar en voz alta.
2. Se cronometra por bloque y se anota **cada pregunta que provoca una duda**.
3. Se registra cada vez que pulsan "preguntárselo a otra persona" y por qué.
4. Al terminar, se les enseña la carpeta de evidencias generada y se pregunta: ¿sabes qué tienes que hacer ahora? Si dudan, el problema son las instrucciones, no ellos.
5. Se les pide que suban tres evidencias reales y se comprueba si aciertan a la primera con los criterios de aceptación.

**Qué medir:**
- Minutos por bloque frente a lo estimado en el seed.
- **Tasa de "preguntárselo a otra persona" por pregunta.** Por encima del 20 %, la pregunta se reescribe (§1bis del cuestionario).
- Preguntas que tuvieron que releer dos veces.
- Evidencias rechazadas en la primera revisión y por qué.

**La señal de alarma:** si abandonan a mitad del perfilado, el producto no funciona por muy buen motor que tenga debajo.

---

## 4. Correos para pedir las sesiones

**Al auditor:**
> Asunto: 1 hora de tu criterio sobre evidencias ENS (pagada)
>
> Hola [nombre]:
>
> Estoy construyendo una herramienta para que los clientes lleguen a la auditoría del ENS con la documentación y las evidencias ya preparadas y ordenadas.
>
> Antes de escribir más código quiero contrastarlo con quien audita de verdad. Tengo una lista de evidencias por medida con lo que creo que rechazaría un auditor, y necesito que alguien me diga dónde me equivoco.
>
> Serían unos 60 minutos, cuando te venga bien, y te la pago como consultoría. Lo que salga se queda en el producto, no en un informe.
>
> ¿Te encaja alguna tarde de las próximas dos semanas?

**Al cliente piloto:**
> Asunto: ¿te ayudo con el ENS a cambio de tu opinión?
>
> Hola [nombre]:
>
> Estoy montando una herramienta que te lleva del desconcierto a la auditoría del ENS: te hace preguntas sobre cómo es tu sistema y te prepara la carpeta de documentación y evidencias que te pedirá el auditor.
>
> Busco dos organizaciones para probarla de verdad. Necesito dos horas tuyas y tu documentación real, y a cambio la usas gratis hasta tu primera auditoría.
>
> No te voy a enseñar una demo: quiero verte usarla y que me digas dónde te atascas.
>
> ¿Te interesa?

---

## 5. Cómo se incorpora lo aprendido

1. **Cada cambio, al seed**, no a una libreta. Los ficheros YAML son la fuente de verdad.
2. **Trazabilidad de la validación:** añadir al frontmatter de cada fichero quién lo revisó y cuándo (`validado_por`, `validado_en`). Cuando un cliente pregunte de dónde sale esto, la respuesta no puede ser "lo escribimos nosotros".
3. **Lo que se contradiga, se decide con datos**, no por antigüedad: si dos auditores discrepan, se mantiene la versión más exigente y se anota la discrepancia en el fichero.
4. **Las estimaciones de tiempo del cuestionario se sustituyen por las medidas** en el piloto.

---

## 6. Señales de que hay que replantear algo

- El auditor dice que prefiere el ZIP y no usaría el portal → **M14 baja de prioridad y M9 sube**.
- Los rechazos típicos le parecen exagerados → el producto está siendo más estricto que la realidad, y eso desanima al cliente sin necesidad.
- El piloto tarda el triple de lo estimado → hay que recortar el cuestionario o repartirlo mejor por roles.
- Nadie quiere el piloto gratis → el problema no es el producto, es que el ENS no duele lo suficiente a ese perfil. Conviene cambiar de perfil objetivo antes que de producto.
