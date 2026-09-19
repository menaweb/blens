"""Carpeta de evidencias (M5/M11): los huecos que hay que rellenar y lo que se aporta.

Cada `EvidenceRequirement` es una plantilla del catálogo instanciada para **este** sistema
porque sus condiciones se cumplen, y recuerda qué respuesta del perfilado lo trajo. Es lo
que convierte «cumple el ENS» en una lista de cosas concretas que alguien puede hacer.

Tres reglas del dominio, en el modelo y no en la vista:

- **Basta una del grupo.** Varias plantillas alternativas cubren el mismo requisito
  (export, captura, informe de un tercero); satisfecha una, las demás quedan como «también
  válidas» y no cuentan como hueco (§4 M5).
- **Una evidencia puede cubrir varios requisitos.** Se sube una vez y se enlaza a todos los
  que cierra: por eso la relación es M2M y no la FK que dibujaba §7.2.
- **Recalcular no borra.** Lo que deja de aplicar pasa a `FUERA_DE_ALCANCE` con sus
  ficheros dentro; si la respuesta vuelve atrás, el requisito se reactiva con lo que tenía.

La vigencia es **por evidencia**, no por medida: la cobertura del antivirus caduca en tres
meses y su política en doce, y las dos cuelgan de op.exp.6.
"""

from __future__ import annotations

from datetime import timedelta

from django.db import models
from django.utils import timezone

from apps.tenancy.models import TenantScopedModel


def ruta_evidencia(instancia: Evidencia, nombre: str) -> str:
    """Dónde vive el fichero. El bucket va con versionado y Object Lock (§11)."""
    return f"evidencias/{instancia.system_id}/{timezone.now():%Y/%m}/{nombre}"


class EstadoRequisito(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    APORTADA = "APORTADA", "Aportada, sin validar"
    VALIDADA = "VALIDADA", "Validada"
    CADUCADA = "CADUCADA", "Caducada"
    FUERA_DE_ALCANCE = "FUERA_DE_ALCANCE", "Fuera de alcance"
    NO_APLICA_JUSTIFICADO = "NO_APLICA_JUSTIFICADO", "No aplica, justificado"


class EstadoEvidencia(models.TextChoices):
    APORTADA = "APORTADA", "Aportada"
    EN_REVISION = "EN_REVISION", "En revisión"
    VALIDADA = "VALIDADA", "Validada"
    RECHAZADA = "RECHAZADA", "Rechazada"
    CADUCADA = "CADUCADA", "Caducada"


class EvidenceRequirement(TenantScopedModel):
    """Un hueco concreto de la carpeta de este sistema."""

    system = models.ForeignKey(
        "compliance.System", on_delete=models.CASCADE, related_name="requisitos_evidencia"
    )
    template = models.ForeignKey(
        "catalog.EvidenceTemplate", on_delete=models.PROTECT, related_name="requisitos"
    )
    estado = models.CharField(
        max_length=25, choices=EstadoRequisito.choices, default=EstadoRequisito.PENDIENTE
    )
    #: Qué hechos y qué preguntas lo dispararon. Es lo que el índice del paquete le enseña
    #: al auditor cuando pregunta por qué está pedido esto (§10bis.4).
    origen = models.JSONField(default=dict, blank=True)
    #: Frase corta para la UI: por qué te lo pedimos.
    motivo = models.CharField(max_length=400, blank=True)

    responsable = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="evidencias_a_cargo",
    )
    fecha_limite = models.DateField(null=True, blank=True)
    #: Cuándo vuelve a hacer falta, según la vigencia de la plantilla.
    proxima_renovacion = models.DateField(null=True, blank=True)
    #: Solo si el cliente lo marca como no aplicable: sin justificación no se puede.
    justificacion = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["template__measure__orden", "template__preferencia", "template__code"]
        constraints = [
            models.UniqueConstraint(
                fields=["system", "template"], name="uniq_requisito_por_plantilla"
            ),
            models.CheckConstraint(
                condition=~models.Q(estado=EstadoRequisito.NO_APLICA_JUSTIFICADO)
                | ~models.Q(justificacion=""),
                name="no_aplica_exige_justificacion",
            ),
        ]
        verbose_name = "requisito de evidencia"
        verbose_name_plural = "requisitos de evidencia"

    def __str__(self) -> str:
        return f"{self.template.code} · {self.get_estado_display()}"

    @property
    def bloque(self) -> str:
        """Acota al COLABORADOR: aporta evidencias de los bloques que le tocan."""
        return ""

    @property
    def cuenta_como_cubierto(self) -> bool:
        """¿Deja de ser un hueco? Lo que está fuera de alcance o justificado, tampoco cuenta."""
        return self.estado in (
            EstadoRequisito.VALIDADA,
            EstadoRequisito.FUERA_DE_ALCANCE,
            EstadoRequisito.NO_APLICA_JUSTIFICADO,
        )

    def renovacion_desde(self, fecha_evidencia) -> None:
        """Fija la próxima renovación a partir de la fecha del hecho, no la de subida."""
        dias = self.template.vigencia_dias
        self.proxima_renovacion = fecha_evidencia + timedelta(days=dias) if dias else None


class Evidencia(TenantScopedModel):
    """Un fichero aportado, con su fecha, su estado y quién respondió por él.

    `fecha_evidencia` es la fecha **del hecho** (cuándo se hizo la prueba de restauración),
    no la de subida: es la que mira el auditor y la que gobierna la caducidad.
    """

    system = models.ForeignKey(
        "compliance.System", on_delete=models.CASCADE, related_name="evidencias"
    )
    #: Una misma evidencia cierra todos los requisitos a los que se enlace.
    requisitos = models.ManyToManyField(EvidenceRequirement, blank=True, related_name="evidencias")
    titulo = models.CharField(max_length=300, blank=True)
    fichero = models.FileField(upload_to=ruta_evidencia, blank=True)
    nombre_original = models.CharField(max_length=300, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    tamano = models.PositiveBigIntegerField(default=0)
    #: Integridad demostrable: el mismo criterio que el versionado documental (§11).
    sha256 = models.CharField(max_length=64, blank=True)

    fecha_evidencia = models.DateField()
    estado = models.CharField(
        max_length=12, choices=EstadoEvidencia.choices, default=EstadoEvidencia.APORTADA
    )
    #: Criterios de aceptación de la plantilla que quien sube declara que se ven.
    criterios_marcados = models.JSONField(default=list, blank=True)
    notas = models.TextField(blank=True)

    aportada_por = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="evidencias_aportadas",
    )
    revisor = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="evidencias_revisadas",
    )
    revisado_en = models.DateTimeField(null=True, blank=True)
    motivo_rechazo = models.TextField(blank=True)
    #: Organización demasiado pequeña para separar funciones: la excepción se registra,
    #: no se ignora (`docs/roles_y_permisos.md` §3).
    excepcion_separacion = models.TextField(blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_evidencia", "-creado_en"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(estado=EstadoEvidencia.RECHAZADA)
                | ~models.Q(motivo_rechazo=""),
                name="rechazo_exige_motivo",
            )
        ]
        verbose_name = "evidencia"
        verbose_name_plural = "evidencias"

    def __str__(self) -> str:
        return self.titulo or self.nombre_original or f"evidencia {self.pk}"
