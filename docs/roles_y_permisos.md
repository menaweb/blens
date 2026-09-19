# Roles y permisos — diseño

> Documento compañero de `CLAUDE.md`. Define quién puede hacer qué. Se decide antes de F1 porque afecta a la primera migración y es caro de añadir después. Relacionado con §14 (aislamiento de tenant) y con M14 (portal del auditor).

---

## 1. Principios

1. **El rol vive en la membresía, no en el usuario.** Una persona puede pertenecer a varias organizaciones (un consultor) con un rol distinto en cada una.
2. **Ámbito por sistema.** Un tenant puede tener varios sistemas en alcance. La membresía puede ser de toda la organización o limitada a sistemas concretos.
3. **Separación de funciones, igual que pide la norma.** Quien aporta una evidencia no la valida; quien redacta un documento no lo aprueba. Es la propia medida op.acc.3 aplicada al producto, y hace que el auditor vea en BLENS una traza creíble.
4. **El catálogo es de solo lectura para todo el mundo.** Medidas, refuerzos, checks, plantillas y CPSTIC no los edita ningún cliente: son datos del sistema.
5. **Todo lo relevante deja traza inmutable**, con quién y cuándo. Sin esto, el paquete de auditoría no vale.
6. **Permiso denegado por defecto.** Lo que no está concedido, no se puede.

---

## 2. Roles

| Rol | Quién es | Para qué |
|---|---|---|
| **Propietario** | Quien contrata BLENS | Todo, más facturación, borrado del tenant e invitaciones. Único que puede transferir la propiedad |
| **Responsable de Seguridad (RSEG)** | El RSEG real de la organización | Aprueba la DdA, valida evidencias, aprueba documentos, acepta riesgos que le correspondan, invita al auditor |
| **Técnico** | Informática interna o proveedor de soporte | Responde el perfilado, sube evidencias, mantiene componentes, activos y riesgos. **No valida ni aprueba** |
| **Colaborador de bloque** | RRHH, instalaciones, legal | Solo los bloques del cuestionario que se le asignen y sus evidencias. No ve el resto |
| **Dirección** | Gerencia, alcaldía, consejo | Solo lectura del panel y los informes, más firma de aprobaciones que le correspondan (política, aceptación de riesgo) |
| **Auditor** | Auditor externo o interno | Solo lectura del paquete, muestreo y peticiones de información (M14). Invitación caducable |
| **Consultor** | Quien acompaña a varios clientes | Como Técnico o RSEG según lo que el cliente le conceda, en los tenants donde tenga membresía. Post-v1 (M10) |
| **Soporte BLENS** | Personal de Anthropic… perdón, de BLENS | Acceso de emergencia, **solo con consentimiento del cliente, con caducidad y traza visible para él**. Ver §5 |

---

## 3. Matriz de permisos

`L` leer · `E` escribir · `A` aprobar o validar · `—` sin acceso

| Objeto | Propietario | RSEG | Técnico | Colaborador | Dirección | Auditor |
|---|---|---|---|---|---|---|
| Categorización | E | E | E | — | L | L |
| Perfilado (responder) | E | E | E | E (sus bloques) | L | L |
| Declaración de Aplicabilidad | E | **A** | E | — | L | L |
| Madurez de las medidas | E | E | E | — | L | L |
| Evidencias: aportar | E | E | E | E (sus bloques) | — | — |
| Evidencias: validar o rechazar | A | **A** | — | — | — | — |
| Documentos: redactar y generar | E | E | E | — | — | — |
| Documentos: aprobar y publicar | A | **A** | — | — | A (los suyos) | L |
| Análisis de riesgos | E | E | E | — | L | L |
| Aceptación del riesgo residual | — | A | — | — | **A** | L |
| Incidentes y plan de acciones | E | E | E | — | L | L |
| Componentes y proveedores | E | E | E | — | L | L |
| Paquete de auditoría (generar) | E | E | E | — | L | L |
| Invitar al auditor | E | E | — | — | — | — |
| Usuarios y roles | E | L | — | — | — | — |
| Facturación y plan | E | — | — | — | — | — |
| Borrar el tenant | E | — | — | — | — | — |
| Catálogo ENS y CPSTIC | L | L | L | L | L | L |

**Reglas de separación que el sistema impone:**
- Quien sube una evidencia **no puede validarla**, aunque tenga el rol. Si solo hay una persona con rol RSEG y ha sido ella quien la subió, la evidencia queda pendiente y se avisa. Es incómodo a propósito: refleja lo que pedirá el auditor.
- Quien redacta un documento no puede aprobarlo.
- La aceptación del riesgo residual la firma Dirección o RSEG, nunca Técnico.
- Si la organización es demasiado pequeña para separar, puede registrar la **excepción justificada** (queda en el paquete como medida compensatoria de op.acc.3, igual que se lo plantearía al auditor).

---

## 4. Modelo de datos

```python
class Membership(Model):
    tenant = FK(Tenant); user = FK(User)
    role = 'PROPIETARIO'|'RSEG'|'TECNICO'|'COLABORADOR'|'DIRECCION'|'AUDITOR'|'CONSULTOR'
    systems = M2M(System, blank=True)     # vacío = todos los del tenant
    bloques: JSON                          # solo COLABORADOR: códigos de bloque asignados
    invited_by; created_at; expires_at = nullable   # AUDITOR y CONSULTOR caducan
    estado = 'ACTIVA'|'PENDIENTE'|'CADUCADA'|'REVOCADA'
    # unique(tenant, user)

class Invitation(Model):
    tenant = FK(Tenant); email; role; systems: JSON; bloques: JSON
    token_hash; expires_at; used_at = nullable; created_by = FK(User)
    # el token nunca se guarda en claro; caducidad obligatoria para AUDITOR

class AuditLog(Model):                     # append-only, con hash encadenado (op.exp.8/9)
    tenant = FK(Tenant, null=True); user = FK(User, null=True)
    accion; objeto_tipo; objeto_id; datos: JSON
    ip; user_agent; created_at; prev_hash; hash
```

**Cómo se comprueba un permiso:** un único punto de acceso (`can(user, accion, objeto)`) que resuelve rol, ámbito de sistema, bloques asignados y reglas de separación. Nada de comprobaciones dispersas por las vistas: cuando llegue el aislamiento de tenant (§14.3), se enchufa ahí.

---

## 5. Acceso de soporte de BLENS

Es el punto más delicado: los clientes son sector público y BLENS aspira a ENS Alto.

- **Nunca por defecto.** El soporte no ve datos de tenant salvo que el cliente lo autorice expresamente desde su panel.
- **Caducidad corta** (por ejemplo 24 horas) y revocable en cualquier momento.
- **Solo lectura por defecto**; la escritura exige un motivo escrito.
- **Traza visible para el cliente**: quién entró, cuándo y qué miró, en su propio registro de actividad, no solo en el nuestro.
- Se documenta en las condiciones del servicio y en el contrato de encargo de tratamiento.

---

## 6. Portal del auditor (M14)

- Membresía de rol `AUDITOR` creada por invitación, **con caducidad obligatoria** y limitada a un sistema.
- Solo lectura sobre el paquete, más dos acciones propias: fijar muestras y abrir peticiones de información.
- No ve: facturación, usuarios, otros sistemas del tenant ni evidencias marcadas como fuera de alcance.
- Todo lo que hace queda en el registro y se conserva con el paquete: el propio expediente de la auditoría demuestra qué revisó.

---

## 7. Pendientes

- [ ] Decidir si Dirección puede ver evidencias con datos personales, o solo los informes. Depende del cliente; probablemente configurable.
- [ ] Definir qué pasa con las evidencias que subió un usuario al que se le revoca el acceso: se conservan, pero hay que decidir cómo se muestra su autoría.
- [ ] Modo consultora (M10): un consultor con varios tenants necesita un selector de cliente y un registro que impida mezclar datos. Depende del aislamiento de tenant.
- [x] Autenticación: **Cognito con MFA**, confirmada el 19/09/2026 en D1 de `docs/decisiones.md`. Cognito **solo autentica**: el rol no viaja en el token ni se mapea a grupos del pool, vive en `Membership` y lo resuelve `can()`. Se cablea en la fase F3b de `docs/plan_construccion.md`.
- [ ] Restablecer el segundo factor de un miembro que lo ha perdido: Cognito no da códigos de recuperación, así que hay que decidir **qué roles pueden hacerlo** (propuesta: PROPIETARIO, y RSEG solo sobre su ámbito) y dejarlo en el registro.
- [ ] Si algún organismo pide federación SAML, decidir entonces cómo se traducen sus grupos a estos roles. Fuera de la v1.
