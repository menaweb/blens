# Decisiones abiertas — análisis y recomendación

> Documento compañero de `CLAUDE.md` §17. Cada decisión lleva opciones, lo que implica cada una, **cuándo hay que decidir** y el **coste de equivocarse**. La recomendación es mía; la decisión es tuya. Cuando se cierre una, se marca aquí y se actualiza §17.

**Estado:** D0, D1, D2 y D6 **decididas** (19/09/2026). Pendientes: D3 precio, D4 UI, D7 CPSTIC, D8 modelo de IA, D9 NIS2.

---

## D0 · Qué es BLENS realmente — ✅ **DECIDIDO: producto SaaS para vender**

Es la decisión de la que cuelgan todas las demás, y no es técnica.

| Opción | Qué implica | Alcance de la v1 |
|---|---|---|
| **A. Producto SaaS para vender** | Registro, planes, cobro, soporte, marketing, y la barra alta de un producto multicliente | M1–M9 completos, más gate de aislamiento |
| **B. Herramienta para tu consultoría** | Un solo usuario (tú), sin registro ni cobro, sin aislamiento, sin portal público | Se cae M1 freemium, M10, M15 y buena parte de la gestión de usuarios. La mitad de trabajo |
| **C. Producto para buscar socio o financiación** | Hace falta demo impecable y un piloto real con nombre, más que cobertura completa | Un camino entero muy pulido (una categoría, una familia), no las 73 medidas a medias |

**Decidido: opción A, producto SaaS.** Descartada la opción B. Recomendación previa (no aceptada): empezar como herramienta propia. Úsalo tú con dos o tres clientes reales de tu consultoría. Resuelve el problema de la validación externa (eres tu propio piloto), genera ingresos mientras se construye y evita meses de trabajo en registro, planes y cobro antes de saber si el producto sirve. La arquitectura ya está preparada: `tenant_id` desde la primera migración y el gate de producción para cuando toque abrirlo.

**Consecuencias de la decisión, que ya no son opinables:**
- La v1 es **M1–M9 completos más M11–M14**, con registro, planes y cobro. Ver D3: el precio pasa a ser decisión de F2, no aplazable.
- **El gate de aislamiento de tenant (§14.3) es obligatorio antes del primer cliente real.** Con la opción B se podía posponer; con esta, no.
- Hacen falta condiciones del servicio, contrato de encargo de tratamiento y lista de subprocesadores desde el primer cliente.
- La validación externa (`docs/validacion_externa.md`) gana peso: sin clientes propios de consultoría, el piloto con dos organizaciones ajenas es la única forma de contrastar el seed antes de vender.
- BLENS debe ser su propio cliente: usar el producto para documentar la conformidad ENS de BLENS. Es la mejor demo y el mejor test.

---

## D1 · Autenticación — ✅ **DECIDIDO: Cognito; Cl@ve y federación SAML fuera**

| Opción | A favor | En contra |
|---|---|---|
| **Cognito** | Todo en AWS, MFA incluido, poco código, soporta SAML como proveedor de identidad federado | Atarse a AWS, personalización limitada, precio por usuario activo |
| **djangosaml2** | Control total, federación con los proveedores de identidad de organismos | Más código y mantenimiento, el MFA hay que resolverlo aparte |

**Decidido: Cognito.** Cl@ve y la federación SAML con proveedores de identidad de organismos quedan descartadas: no tienen sentido para este producto. Cubre lo que necesitas ya (correo, contraseña y MFA) y admite federación SAML después para los organismos que la pidan, sin rehacerlo. Con la opción B de D0, esto es aún más claro: no merece mantener infraestructura de identidad propia para pocos usuarios.

**Por qué Cl@ve queda fuera, para cuando lo pregunte un cliente:** **Cl@ve está pensada para que la ciudadanía se identifique ante las administraciones**, y la adhesión es de organismos públicos, no de un SaaS privado. Habría que integrarse en nombre del organismo, si es que es posible. Además, y esto es lo importante: BLENS no necesita Cl@ve. Quien usa BLENS es el personal de la organización, no el ciudadano. Cl@ve aparece como **respuesta del cliente** en op.acc.5 (cómo se identifican sus usuarios externos), no como forma de entrar a BLENS.

---

## D2 · Región — ✅ **DECIDIDO: eu-west-1 (Irlanda)**

| Opción | A favor | En contra |
|---|---|---|
| **eu-south-2 (Zaragoza)** | Argumento de venta directo: "tus datos en España". Imbatible en pliegos públicos | Menos servicios disponibles y a veces con retraso; algún servicio puede no estar |
| **eu-west-1 (Irlanda)** | Todos los servicios, más madura, más barata | "En la UE" es correcto, pero el pliego que diga España te deja fuera |

**Decidido: eu-west-1 (Irlanda).** El requisito es que los datos estén **en la Unión Europea**, no necesariamente en España. A cambio se gana madurez, catálogo completo de servicios y menor coste.

**Cómo se cuenta al cliente:** "datos alojados en la Unión Europea, sin transferencias internacionales". Es cierto y suficiente para el RGPD y para la mayoría de pliegos.

**Riesgo asumido, para tenerlo presente:** un pliego que exija expresamente territorio español dejaría a BLENS fuera. Si aparece esa demanda de forma repetida, se valora una segunda región; el diseño no lo impide, pero es una migración.

**Ventaja añadida:** eu-west-1 es de las regiones más completas, así que decae la comprobación de disponibilidad de servicios que habría hecho falta con eu-south-2, incluida la de Bedrock para M16 (D8).

---

## D3 · Precio y modelo comercial  ⏰ antes de F2 (M1 freemium lo toca)

El mercado que ya conocemos: las herramientas del CCN son gratuitas, Cumpleo cobra decenas de euros al año, los packs de consultoría con software rondan miles de euros, y las GRC internacionales van de seis mil a veinticinco mil, sin precio público.

**Recomendación: precio público, tres planes, entre Cumpleo y los packs de consultoría.**
- **Gratis:** categorización y su PDF. Sin registro. Es el gancho.
- **Básico:** una organización, un sistema, categoría Básica.
- **Completo:** Media y Alta, varios sistemas, portal del auditor.
- **Consultora** (post-v1): varios clientes.

Dos compromisos que os diferencian de Vanta y Drata, que es exactamente donde más se quejan sus usuarios: **precio público y renovación garantizada sin subidas sorpresa**.

Con la opción B de D0, esto se pospone: cobras por tu servicio de consultoría, no por el software.

---

## D4 · Interfaz del frontend  ⏰ antes de F2

shadcn-vue frente a PrimeVue. **Recomendación: shadcn-vue**, porque controlas el diseño y el brief (`docs/brief_diseno.md`) pide una identidad propia, no un panel genérico. El punto débil es el data-grid: si el checklist de medidas o la tabla de riesgos se quedan cortos, se puede meter una tabla especializada solo ahí. Es reversible por componente, así que no es una decisión cara.

---

## D5 · Infraestructura como código  ⏰ antes de F0

Ya decidido: CDK en Python. **Manténlo.** Mismo lenguaje que el backend, una cosa menos que aprender. Terraform solo tendría sentido si entrara alguien que ya lo domina.

---

## D6 · Marca — ✅ **DECIDIDO: BLENS**

Existe "BL España Software / Berger-Levrault", con certificado ENS de categoría Alta. No es competidor directo (hace software de gestión pública), pero opera en el mismo mercado y ante los mismos compradores.

**Decidido: se usa BLENS**, verificado como libre.

**Lo que conviene hacer ahora que está decidido:** registrar el dominio y valorar el registro de marca en la OEPM (clases 9 y 42). Cuesta poco y evita que alguien lo registre después. Si en algún momento aparece confusión comercial con "BL España Software / Berger-Levrault", el registro es lo que resuelve la conversación.

---

## D7 · Explotación del CPSTIC  ⏰ antes de exponer la función a clientes

Ya hay criterio en §3.2.0: solo campos fácticos, citando la fuente y sin redistribuir. **Recomendación: mantener el criterio, consultar con asesoría y mandar un correo informativo al CCN.** No pidas permiso como si dudaras de tu derecho: informa de lo que haces y pregunta si existe formato estructurado. De paso abres relación con ellos, que es útil si algún día quieres estar en el apartado 9 del catálogo.

---

## D8 · Proveedor de modelo para M16  ⏰ post-v1

**Recomendación: Bedrock en eu-west-1**, la misma región del despliegue (D2), con retención cero, sin uso para entrenamiento y desactivable por tenant. Al estar todo en Irlanda desaparece la complicación de repartir el tratamiento entre regiones.

---

## D9 · NIS2  ⏰ antes de mencionarla en el producto

**No la menciones hasta verificar el estado de la transposición española.** Es un reclamo comercial fácil y un problema si un cliente te pregunta por el detalle y no cuadra. Cuando se confirme, entra como marco adicional en la fase F6 (mapeo multimarco), no antes.

---

## Resumen

| # | Decisión | Recomendación | Cuándo | Coste de equivocarse |
|---|---|---|---|---|
| D0 | Qué es BLENS | ✅ Producto SaaS para vender | Decidido | — |
| D1 | Autenticación | ✅ Cognito; Cl@ve y SAML fuera | Decidido | — |
| D2 | Región | ✅ eu-west-1 (Irlanda), datos en la UE | Decidido | — |
| D3 | Precio | Público, tres planes, renovación garantizada | **Antes de F2 (ahora prioritario por D0)** | Medio |
| D4 | UI | shadcn-vue | Antes de F2 | Bajo |
| D5 | IaC | CDK Python (ya decidido) | — | Bajo |
| D6 | Marca | ✅ BLENS (libre); registrar dominio y marca | Decidido | — |
| D7 | CPSTIC | Campos fácticos, asesoría y aviso al CCN | Antes de exponerlo | Medio |
| D8 | Modelo de IA | Bedrock en la región del despliegue | Post-v1 | Bajo |
| D9 | NIS2 | No mencionarla hasta verificar | Antes de anunciarlo | Bajo, pero de credibilidad |
