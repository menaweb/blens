"""Organización cliente, membresías, invitaciones y registro de actividad.

Tres cosas que conviene tener claras antes de tocar esto:

1. `TenantScopedModel` lleva `tenant` **nullable y sin filtrar** (§14.2). Es andamiaje
   para que el aislamiento sea aditivo más adelante; hoy NO aísla nada.
2. El rol vive en la membresía, no en el usuario: una persona puede estar en varias
   organizaciones con rol distinto (`docs/roles_y_permisos.md` §1).
3. `AuditLog` es append-only con hash encadenado (op.exp.8/9). No se edita ni se borra.
"""

import hashlib
import json
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


class Tenant(models.Model):
    """Organización cliente."""

    nombre = models.CharField(max_length=200)
    cif = models.CharField(max_length=20, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "organización"
        verbose_name_plural = "organizaciones"

    def __str__(self) -> str:
        return self.nombre


class TenantScopedModel(models.Model):
    """Base de todo modelo que contiene datos de un cliente.

    ⚠️ `tenant` es nullable y NO se filtra en v1 (§14.2). El gate de producción (§14.3)
    lo pondrá NOT NULL, añadirá el manager con ámbito y la RLS de PostgreSQL. Heredar de
    aquí es lo que hace que ese cambio sea aditivo en lugar de una migración de datos.
    """

    tenant = models.ForeignKey(Tenant, null=True, blank=True, on_delete=models.CASCADE)

    class Meta:
        abstract = True


class Role(models.TextChoices):
    PROPIETARIO = "PROPIETARIO", "Propietario"
    RSEG = "RSEG", "Responsable de Seguridad"
    TECNICO = "TECNICO", "Técnico"
    COLABORADOR = "COLABORADOR", "Colaborador de bloque"
    DIRECCION = "DIRECCION", "Dirección"
    AUDITOR = "AUDITOR", "Auditor"
    CONSULTOR = "CONSULTOR", "Consultor"


#: Roles cuya membresía caduca obligatoriamente (`docs/roles_y_permisos.md` §2).
ROLES_CADUCABLES = (Role.AUDITOR, Role.CONSULTOR)


class MembershipEstado(models.TextChoices):
    ACTIVA = "ACTIVA", "Activa"
    PENDIENTE = "PENDIENTE", "Pendiente"
    CADUCADA = "CADUCADA", "Caducada"
    REVOCADA = "REVOCADA", "Revocada"


class Membership(models.Model):
    """Pertenencia de una persona a una organización, con su rol y su ámbito."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    #: Vacío = todos los sistemas del tenant.
    systems = models.ManyToManyField("compliance.System", blank=True, related_name="memberships")
    #: Solo COLABORADOR: códigos de bloque del cuestionario asignados. Vacío = ninguno.
    bloques = models.JSONField(default=list, blank=True)
    estado = models.CharField(
        max_length=12, choices=MembershipEstado.choices, default=MembershipEstado.ACTIVA
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invitaciones_emitidas",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "user"], name="uniq_membership_tenant_user")
        ]
        verbose_name = "membresía"
        verbose_name_plural = "membresías"

    def __str__(self) -> str:
        return f"{self.user} · {self.get_role_display()} en {self.tenant}"

    def clean(self) -> None:
        if self.role in ROLES_CADUCABLES and self.expires_at is None:
            raise ValidationError(
                {"expires_at": "Las membresías de auditor y consultor caducan obligatoriamente."}
            )

    @property
    def caducada(self) -> bool:
        return self.expires_at is not None and self.expires_at <= timezone.now()

    @property
    def vigente(self) -> bool:
        return self.estado == MembershipEstado.ACTIVA and not self.caducada


class Invitation(models.Model):
    """Invitación por correo. El token solo existe en claro al emitirla."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="invitaciones")
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=Role.choices)
    systems = models.JSONField(default=list, blank=True)
    bloques = models.JSONField(default=list, blank=True)
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "invitación"
        verbose_name_plural = "invitaciones"

    def __str__(self) -> str:
        return f"{self.email} · {self.get_role_display()} en {self.tenant}"

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    def issue(cls, *, tenant, email, role, created_by=None, dias=7, **extra):
        """Crea la invitación y devuelve `(invitacion, token_en_claro)`.

        El token en claro se envía por correo y no vuelve a existir: en base de datos
        solo queda su sha256.
        """
        token = secrets.token_urlsafe(32)
        inv = cls.objects.create(
            tenant=tenant,
            email=email,
            role=role,
            created_by=created_by,
            token_hash=cls.hash_token(token),
            expires_at=timezone.now() + timedelta(days=dias),
            **extra,
        )
        return inv, token

    @property
    def vigente(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()


class AuditLog(models.Model):
    """Registro de actividad append-only con hash encadenado (op.exp.8/9, §13).

    La cadena es **por organización** (las entradas sin tenant forman su propia cadena),
    para que el expediente que se entrega al auditor sea verificable por sí solo.
    """

    tenant = models.ForeignKey(Tenant, null=True, blank=True, on_delete=models.SET_NULL)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    accion = models.CharField(max_length=100)
    objeto_tipo = models.CharField(max_length=100, blank=True)
    objeto_id = models.CharField(max_length=64, blank=True)
    datos = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    prev_hash = models.CharField(max_length=64, blank=True)
    hash = models.CharField(max_length=64)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["tenant", "id"])]
        verbose_name = "entrada del registro"
        verbose_name_plural = "registro de actividad"

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M} · {self.accion}"

    def compute_hash(self) -> str:
        """sha256 del contenido + el hash anterior. Cualquier retoque rompe la cadena."""
        payload = {
            "prev": self.prev_hash,
            "tenant": self.tenant_id,
            "user": self.user_id,
            "accion": self.accion,
            "objeto_tipo": self.objeto_tipo,
            "objeto_id": self.objeto_id,
            "datos": self.datos,
            "created_at": self.created_at.isoformat(),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    @transaction.atomic
    def append(
        cls, *, accion, tenant=None, user=None, objeto=None, datos=None, ip=None, user_agent=""
    ):
        """Añade una entrada al final de la cadena de su organización."""
        ultimo = cls.objects.select_for_update().filter(tenant=tenant).order_by("-id").first()
        entrada = cls(
            tenant=tenant,
            user=user,
            accion=accion,
            objeto_tipo=objeto.__class__.__name__ if objeto is not None else "",
            objeto_id=str(getattr(objeto, "pk", "") or ""),
            datos=datos or {},
            ip=ip,
            user_agent=user_agent,
            prev_hash=ultimo.hash if ultimo else "",
        )
        entrada.hash = entrada.compute_hash()
        entrada.save()
        return entrada

    @classmethod
    def verify_chain(cls, tenant=None):
        """Devuelve `(True, None)` si la cadena es íntegra, o `(False, pk)` del primer roto."""
        prev = ""
        for entrada in cls.objects.filter(tenant=tenant).order_by("id"):
            if entrada.prev_hash != prev or entrada.hash != entrada.compute_hash():
                return False, entrada.pk
            prev = entrada.hash
        return True, None
