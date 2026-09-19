"""Punto **único** de decisión de permisos: `can(user, accion, objeto)`.

Ninguna vista, tarea o serializador comprueba roles por su cuenta (§15). Todo pasa por
aquí, y aquí es donde se enchufará el aislamiento de tenant cuando llegue el gate de
producción (§14.3).

Tres capas de decisión, en este orden:

1. **Membresía vigente** en la organización del objeto (rol, estado y caducidad).
2. **Matriz de permisos** de `docs/roles_y_permisos.md` §3, más el ámbito por sistema y,
   para el rol COLABORADOR, los bloques asignados.
3. **Separación de funciones**, que puede denegar lo que la matriz concede: quien aporta
   una evidencia no la valida y quien redacta un documento no lo aprueba, aunque su rol
   se lo permitiría.

El superusuario de Django **no** salta ninguna comprobación: el acceso del soporte de
BLENS exige consentimiento del cliente, caducidad y traza (`docs/roles_y_permisos.md` §5),
no un interruptor global.
"""

from __future__ import annotations

from django.core.exceptions import PermissionDenied

from apps.tenancy.models import Membership, Role

#: Niveles de la matriz: leer < escribir < aprobar.
LEER, ESCRIBIR, APROBAR = "L", "E", "A"
_ORDEN = {LEER: 1, ESCRIBIR: 2, APROBAR: 3}

#: `docs/roles_y_permisos.md` §3, literal. Lo que no aparece, no se puede (denegado por defecto).
MATRIZ: dict[str, dict[str, str]] = {
    "categorizacion": {
        Role.PROPIETARIO: "E",
        Role.RSEG: "E",
        Role.TECNICO: "E",
        Role.DIRECCION: "L",
        Role.AUDITOR: "L",
    },
    "perfilado": {
        Role.PROPIETARIO: "E",
        Role.RSEG: "E",
        Role.TECNICO: "E",
        Role.COLABORADOR: "E",
        Role.DIRECCION: "L",
        Role.AUDITOR: "L",
    },
    "dda": {
        Role.PROPIETARIO: "E",
        Role.RSEG: "A",
        Role.TECNICO: "E",
        Role.DIRECCION: "L",
        Role.AUDITOR: "L",
    },
    "madurez": {
        Role.PROPIETARIO: "E",
        Role.RSEG: "E",
        Role.TECNICO: "E",
        Role.DIRECCION: "L",
        Role.AUDITOR: "L",
    },
    "evidencia_aportar": {
        Role.PROPIETARIO: "E",
        Role.RSEG: "E",
        Role.TECNICO: "E",
        Role.COLABORADOR: "E",
    },
    "evidencia_validar": {Role.PROPIETARIO: "A", Role.RSEG: "A"},
    "documento_redactar": {Role.PROPIETARIO: "E", Role.RSEG: "E", Role.TECNICO: "E"},
    "documento_aprobar": {
        Role.PROPIETARIO: "A",
        Role.RSEG: "A",
        Role.DIRECCION: "A",
        Role.AUDITOR: "L",
    },
    "riesgo": {
        Role.PROPIETARIO: "E",
        Role.RSEG: "E",
        Role.TECNICO: "E",
        Role.DIRECCION: "L",
        Role.AUDITOR: "L",
    },
    "riesgo_aceptar": {Role.RSEG: "A", Role.DIRECCION: "A", Role.AUDITOR: "L"},
    "incidentes": {
        Role.PROPIETARIO: "E",
        Role.RSEG: "E",
        Role.TECNICO: "E",
        Role.DIRECCION: "L",
        Role.AUDITOR: "L",
    },
    "componentes": {
        Role.PROPIETARIO: "E",
        Role.RSEG: "E",
        Role.TECNICO: "E",
        Role.DIRECCION: "L",
        Role.AUDITOR: "L",
    },
    "paquete": {
        Role.PROPIETARIO: "E",
        Role.RSEG: "E",
        Role.TECNICO: "E",
        Role.DIRECCION: "L",
        Role.AUDITOR: "L",
    },
    "auditor_invitar": {Role.PROPIETARIO: "E", Role.RSEG: "E"},
    "usuarios": {Role.PROPIETARIO: "E", Role.RSEG: "L"},
    "facturacion": {Role.PROPIETARIO: "E"},
    "tenant_borrar": {Role.PROPIETARIO: "E"},
    # El catálogo (medidas, refuerzos, checks, plantillas, CPSTIC) es dato del sistema:
    # solo lectura para todo el mundo, incluido el propietario.
    "catalogo": {r: "L" for r in Role.values},
}

#: Acción → (fila de la matriz, nivel necesario). Es el vocabulario que usan las vistas.
ACCIONES: dict[str, tuple[str, str]] = {
    "categorizacion.leer": ("categorizacion", LEER),
    "categorizacion.editar": ("categorizacion", ESCRIBIR),
    "perfilado.leer": ("perfilado", LEER),
    "perfilado.responder": ("perfilado", ESCRIBIR),
    "dda.leer": ("dda", LEER),
    "dda.editar": ("dda", ESCRIBIR),
    "dda.aprobar": ("dda", APROBAR),
    "madurez.leer": ("madurez", LEER),
    "madurez.editar": ("madurez", ESCRIBIR),
    "evidencia.aportar": ("evidencia_aportar", ESCRIBIR),
    "evidencia.validar": ("evidencia_validar", APROBAR),
    "evidencia.rechazar": ("evidencia_validar", APROBAR),
    # Ver una evidencia va con el paquete de auditoría, no con la fila de aportar:
    # el auditor y dirección leen el expediente. Pendiente afinarlo para evidencias con
    # datos personales (docs/roles_y_permisos.md §7).
    "evidencia.leer": ("paquete", LEER),
    "documento.redactar": ("documento_redactar", ESCRIBIR),
    "documento.aprobar": ("documento_aprobar", APROBAR),
    "documento.leer": ("documento_aprobar", LEER),
    "riesgo.leer": ("riesgo", LEER),
    "riesgo.editar": ("riesgo", ESCRIBIR),
    "riesgo.aceptar": ("riesgo_aceptar", APROBAR),
    "incidente.leer": ("incidentes", LEER),
    "incidente.editar": ("incidentes", ESCRIBIR),
    "componente.leer": ("componentes", LEER),
    "componente.editar": ("componentes", ESCRIBIR),
    "paquete.leer": ("paquete", LEER),
    "paquete.generar": ("paquete", ESCRIBIR),
    "auditor.invitar": ("auditor_invitar", ESCRIBIR),
    "usuarios.leer": ("usuarios", LEER),
    "usuarios.gestionar": ("usuarios", ESCRIBIR),
    "facturacion.gestionar": ("facturacion", ESCRIBIR),
    "tenant.borrar": ("tenant_borrar", ESCRIBIR),
    "catalogo.leer": ("catalogo", LEER),
}

#: Separación de funciones: acción → atributos del objeto que identifican a quien la originó.
AUTORIA = {
    "evidencia.validar": ("aportada_por_id", "subida_por_id"),
    "evidencia.rechazar": ("aportada_por_id", "subida_por_id"),
    "documento.aprobar": ("autor_id", "redactado_por_id"),
}

#: Recursos que el COLABORADOR tiene acotados a los bloques que se le asignen. El resto de
#: lo que puede ver (el catálogo) no depende de bloque alguno.
RECURSOS_POR_BLOQUE = {"perfilado", "evidencia_aportar"}

#: El consultor actúa con el rol que el cliente le conceda; por defecto, el de Técnico (M10).
ROL_EFECTIVO = {Role.CONSULTOR: Role.TECNICO}


def _attr(objeto, *nombres):
    for nombre in nombres:
        valor = getattr(objeto, nombre, None)
        if valor is not None:
            return valor
    return None


def _tenant_id(objeto, tenant):
    if tenant is not None:
        return getattr(tenant, "pk", tenant)
    from apps.tenancy.models import Tenant

    if isinstance(objeto, Tenant):
        return objeto.pk
    return _attr(objeto, "tenant_id")


def _system_id(objeto):
    from apps.compliance.models import System

    if isinstance(objeto, System):
        return objeto.pk
    return _attr(objeto, "system_id", "sistema_id")


def membership_of(user, tenant_id) -> Membership | None:
    """Membresía vigente de `user` en esa organización, o None."""
    if user is None or not getattr(user, "is_authenticated", False) or tenant_id is None:
        return None
    m = Membership.objects.filter(user=user, tenant_id=tenant_id).first()
    return m if m is not None and m.vigente else None


def can(user, accion: str, objeto=None, *, tenant=None) -> bool:
    """¿Puede `user` hacer `accion` sobre `objeto`?

    `objeto` puede ser cualquier cosa con `tenant_id` (y opcionalmente `system_id` o
    `bloque`): un modelo, o un objeto simple en los tests. `tenant` se pasa cuando la
    acción no recae sobre un objeto concreto (por ejemplo `facturacion.gestionar`).
    """
    if accion not in ACCIONES:
        raise ValueError(f"Acción desconocida: {accion!r}. Añádela a ACCIONES.")
    recurso, nivel = ACCIONES[accion]

    membership = membership_of(user, _tenant_id(objeto, tenant))
    if membership is None:
        return False

    rol = ROL_EFECTIVO.get(membership.role, membership.role)
    concedido = MATRIZ[recurso].get(rol)
    if concedido is None or _ORDEN[concedido] < _ORDEN[nivel]:
        return False

    # Ámbito por sistema: membresía sin sistemas = toda la organización.
    system_id = _system_id(objeto)
    if system_id is not None and membership.systems.exists():
        if not membership.systems.filter(pk=system_id).exists():
            return False

    # El colaborador solo ve los bloques que se le hayan asignado.
    if rol == Role.COLABORADOR and recurso in RECURSOS_POR_BLOQUE:
        bloque = _attr(objeto, "bloque", "bloque_code")
        if bloque is None or bloque not in (membership.bloques or []):
            return False

    # Separación de funciones: puede denegar lo que la matriz concede.
    if accion in AUTORIA and not getattr(objeto, "excepcion_separacion", None):
        if _attr(objeto, *AUTORIA[accion]) == user.pk:
            return False

    return True


def require(user, accion: str, objeto=None, *, tenant=None) -> None:
    """Como `can`, pero levanta `PermissionDenied`. Es lo que usan las vistas."""
    if not can(user, accion, objeto, tenant=tenant):
        raise PermissionDenied(f"Sin permiso para {accion}.")
