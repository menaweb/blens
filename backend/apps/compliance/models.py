"""Sistemas bajo alcance, categorización (M1) y Declaración de Aplicabilidad (M2).

La categorización guarda el **nivel de cada dimensión**, no solo la categoría resultante
(§3): la aplicabilidad se deriva por dimensión, y una dimensión que no marca la categoría
conserva su nivel (Anexo I.4.2).

La DdA no calcula nada por su cuenta: sale de `engines.ens_applicability` y guarda una
**instantánea** de la categoría, los niveles y la versión del catálogo con que se generó,
para que aprobar algo hoy y cambiar la categorización mañana no reescriba el pasado.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.tenancy.models import TenantScopedModel
from engines.oscal_io.models import ORDEN_NIVEL


class Categoria(models.TextChoices):
    BASICA = "BASICA", "Básica"
    MEDIA = "MEDIA", "Media"
    ALTA = "ALTA", "Alta"


class System(TenantScopedModel):
    """Sistema de información bajo alcance del ENS."""

    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    #: Se deriva de la valoración por dimensiones (Anexo I); vacía hasta categorizar (M1).
    categoria = models.CharField(max_length=10, choices=Categoria.choices, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "sistema"
        verbose_name_plural = "sistemas"

    def __str__(self) -> str:
        return self.nombre


class Dimension(models.TextChoices):
    """ACIDA. El orden es el del Anexo I."""

    C = "C", "Confidencialidad"
    I = "I", "Integridad"  # noqa: E741
    T = "T", "Trazabilidad"
    A = "A", "Autenticidad"
    D = "D", "Disponibilidad"


class Nivel(models.TextChoices):
    NA = "NA", "No aplica"
    BAJO = "BAJO", "Bajo"
    MEDIO = "MEDIO", "Medio"
    ALTO = "ALTO", "Alto"


#: Madurez mínima por categoría (CCN-STIC-815).
MADUREZ_MINIMA = {"BASICA": 2, "MEDIA": 3, "ALTA": 4}


class DimensionValuation(models.Model):
    """Nivel de impacto de una dimensión para un sistema (M1)."""

    system = models.ForeignKey(System, on_delete=models.CASCADE, related_name="valoraciones")
    dim = models.CharField(max_length=1, choices=Dimension.choices)
    nivel = models.CharField(max_length=5, choices=Nivel.choices, default=Nivel.NA)
    justificacion = models.TextField(blank=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["system", "dim"], name="uniq_valoracion_por_dimension")
        ]
        verbose_name = "valoración de dimensión"
        verbose_name_plural = "valoraciones de dimensiones"

    def __str__(self) -> str:
        return f"{self.get_dim_display()}: {self.get_nivel_display()}"


def categoria_de(niveles: dict[str, str]) -> str:
    """Anexo I: la categoría es la mayor de las dimensiones.

    Si todas son «no aplica» no hay categoría: el alcance está mal delimitado y hay que
    decirlo, no inventar una Básica (regla de la pantalla de categorización del handoff).
    """
    mayor = max((ORDEN_NIVEL.get(n, 0) for n in niveles.values()), default=0)
    return {0: "", 1: "BASICA", 2: "MEDIA", 3: "ALTA"}[mayor]


class EstadoDda(models.TextChoices):
    BORRADOR = "BORRADOR", "Borrador"
    EN_REVISION = "EN_REVISION", "En revisión"
    APROBADA = "APROBADA", "Aprobada"
    OBSOLETA = "OBSOLETA", "Obsoleta"


class DeclaracionAplicabilidad(TenantScopedModel):
    """Una versión de la DdA. Inmutable en lo esencial una vez aprobada."""

    system = models.ForeignKey(System, on_delete=models.CASCADE, related_name="declaraciones")
    version = models.PositiveIntegerField()
    estado = models.CharField(max_length=12, choices=EstadoDda.choices, default=EstadoDda.BORRADOR)

    # Instantánea de las condiciones con las que se generó.
    catalog = models.ForeignKey("catalog.CatalogVersion", on_delete=models.PROTECT)
    categoria = models.CharField(max_length=10)
    niveles = models.JSONField(default=dict)

    creada_por = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="ddas_creadas"
    )
    creada_en = models.DateTimeField(auto_now_add=True)
    aprobador = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="ddas_aprobadas"
    )
    aprobada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-version"]
        constraints = [
            models.UniqueConstraint(fields=["system", "version"], name="uniq_dda_por_sistema")
        ]
        verbose_name = "declaración de aplicabilidad"
        verbose_name_plural = "declaraciones de aplicabilidad"

    def __str__(self) -> str:
        return f"DdA v{self.version} · {self.system}"

    @property
    def madurez_minima(self) -> int:
        return MADUREZ_MINIMA.get(self.categoria, 0)

    def problemas(self) -> list[str]:
        """Lo que impide aprobarla. Lista vacía = lista para aprobar."""
        pendientes = []
        for aplicada in self.medidas.all():
            if not aplicada.aplica and not aplicada.justificacion.strip():
                pendientes.append(
                    f"{aplicada.measure.code}: marcada como no aplicable sin justificar"
                )
            sin_resolver = [
                param for param, elegido in (aplicada.selecciones or {}).items() if not elegido
            ]
            for param in sorted(sin_resolver):
                pendientes.append(
                    f"{aplicada.measure.code}: selección de refuerzo sin resolver ({param})"
                )
        return pendientes

    def aprobar(self, usuario) -> None:
        """Aprueba la DdA. El permiso se comprueba **antes**, en la vista, con `can()`."""
        if self.estado == EstadoDda.APROBADA:
            raise ValidationError("Esta declaración ya está aprobada.")
        problemas = self.problemas()
        if problemas:
            raise ValidationError(problemas)
        anteriores = DeclaracionAplicabilidad.objects.filter(
            system=self.system, estado=EstadoDda.APROBADA
        ).exclude(pk=self.pk)
        anteriores.update(estado=EstadoDda.OBSOLETA)
        self.estado = EstadoDda.APROBADA
        self.aprobador = usuario
        self.aprobada_en = timezone.now()
        self.save(update_fields=["estado", "aprobador", "aprobada_en"])


class MeasureApplied(models.Model):
    """Decisión sobre una medida dentro de una DdA."""

    dda = models.ForeignKey(
        DeclaracionAplicabilidad, on_delete=models.CASCADE, related_name="medidas"
    )
    measure = models.ForeignKey("catalog.EnsMeasure", on_delete=models.PROTECT)
    aplica = models.BooleanField(default=True)
    #: Por qué lo dice el catálogo ("categoría MEDIA", "nivel de dimensión (I=ALTO)").
    motivo = models.CharField(max_length=200, blank=True)
    #: Obligatoria cuando se marca como no aplicable una medida que el catálogo exige.
    justificacion = models.TextField(blank=True)
    compensatoria = models.TextField(blank=True)

    refuerzos_obligatorios = models.JSONField(default=list, blank=True)
    refuerzos_opcionales = models.JSONField(default=list, blank=True)
    refuerzos_elegidos = models.JSONField(default=list, blank=True)
    #: {param_id: refuerzo elegido | ""} — vacío = sin resolver, y bloquea la aprobación.
    selecciones = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["measure__orden"]
        constraints = [
            models.UniqueConstraint(fields=["dda", "measure"], name="uniq_medida_por_dda")
        ]
        verbose_name = "medida de la DdA"
        verbose_name_plural = "medidas de la DdA"

    def __str__(self) -> str:
        return f"{self.measure.code} · {'aplica' if self.aplica else 'no aplica'}"


class InformeCategorizacion(models.Model):
    """Resultado de la categorización gratuita (M1), con o sin cuenta.

    Se guarda para poder generar el PDF en Celery y descargarlo después. Si no hay
    tenant es una categorización anónima: **caduca**, porque son datos de alguien que
    todavía no es cliente.
    """

    token = models.UUIDField(unique=True)
    tenant = models.ForeignKey("tenancy.Tenant", null=True, blank=True, on_delete=models.CASCADE)
    system = models.ForeignKey(System, null=True, blank=True, on_delete=models.SET_NULL)
    organizacion = models.CharField(max_length=200, blank=True)
    alcance = models.CharField(max_length=300, blank=True)
    niveles = models.JSONField(default=dict)
    categoria = models.CharField(max_length=10, blank=True)
    resumen = models.JSONField(default=dict)  # cifras y desglose que se enseñan
    pdf = models.FileField(upload_to="categorizaciones/", blank=True)
    estado = models.CharField(max_length=12, default="PENDIENTE")  # PENDIENTE|LISTO|ERROR
    creado_en = models.DateTimeField(auto_now_add=True)
    expira_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "informe de categorización"
        verbose_name_plural = "informes de categorización"

    def __str__(self) -> str:
        return f"{self.organizacion or 'anónima'} · {self.categoria or 'sin determinar'}"

    @property
    def caducado(self) -> bool:
        return self.expira_en is not None and self.expira_en <= timezone.now()


class MeasureAssessment(TenantScopedModel):
    """**Fuente única de la madurez de una medida** (§15).

    Es el modelo más importante del producto después del catálogo: de aquí salen a la
    vez el índice de cumplimiento (`engines.scoring_engine`) y la eficacia de la
    salvaguarda en el riesgo residual (`engines.risk_engine`). Nadie más guarda una
    madurez; si alguna vista necesita una, la lee de aquí.

    Lo que el cliente declara y lo que puede demostrar son cosas distintas: el nivel
    vive aquí y la evidencia que lo sostiene llegará en F4. Hasta entonces
    `madurez_soportada` responde siempre que sí, y está aislado en un único sitio para
    que enchufar las evidencias sea cambiar este método y nada más.
    """

    system = models.ForeignKey(System, on_delete=models.CASCADE, related_name="valoraciones_medida")
    measure = models.ForeignKey("catalog.EnsMeasure", on_delete=models.PROTECT)
    #: L0-L5 de la CCN-STIC-815. Nulo = nadie la ha valorado todavía, que no es L0.
    maturity_level = models.PositiveSmallIntegerField(null=True, blank=True)
    #: Objetivo propio; vacío = el mínimo que exige la categoría del sistema.
    objetivo = models.PositiveSmallIntegerField(null=True, blank=True)
    applies = models.BooleanField(default=True)

    responsable = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="medidas_a_cargo",
    )
    fecha_limite = models.DateField(null=True, blank=True)
    notas = models.TextField(blank=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["measure__orden"]
        constraints = [
            models.UniqueConstraint(fields=["system", "measure"], name="uniq_madurez_por_medida"),
            models.CheckConstraint(
                condition=models.Q(maturity_level__lte=5),
                name="madurez_dentro_de_la_escala",
            ),
            models.CheckConstraint(
                condition=models.Q(objetivo__lte=5),
                name="objetivo_dentro_de_la_escala",
            ),
        ]
        verbose_name = "valoración de madurez"
        verbose_name_plural = "valoraciones de madurez"

    def __str__(self) -> str:
        nivel = "sin valorar" if self.maturity_level is None else f"L{self.maturity_level}"
        return f"{self.measure.code} · {nivel}"

    @property
    def madurez_soportada(self) -> bool:
        """¿Hay evidencia validada que sostenga el nivel declarado? (M5).

        Es lo primero que mira un auditor: una medida en L3 que nadie puede demostrar
        vale L0 en la auditoría. Por debajo de L2 no se exige evidencia, y una medida a la
        que el perfilado todavía no ha pedido nada cuenta como soportada.

        Cómoda para una medida suelta, pero hace consultas: el checklist y el dashboard
        resuelven el sistema entero de una vez en `apps.compliance.services`.
        """
        from apps.evidence.services import madurez_soportada

        return madurez_soportada(self.system, self.measure.code, self.maturity_level)
