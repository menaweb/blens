"""Análisis de riesgos MAGERIT: activos, dependencias, amenazas y resultados (M7).

Aquí no se calcula nada. El cálculo vive en `engines.risk_engine`, que es puro y
determinista; estos modelos guardan lo que el cliente describe y lo que el motor
devuelve, para poder enseñarlo sin recalcular y para que un informe firmado hace seis
meses siga diciendo lo que decía.

Dos decisiones que conviene no tocar sin pensarlas:

- **Todo en `NUMERIC`** (`DecimalField`), nunca coma flotante (§15). El análisis acaba en
  un informe auditable: mismo input, mismo output.
- **`RiskResult` es una foto, no un dato de entrada.** Se borra y se reescribe entera en
  cada recálculo, con `computed_at` y la madurez que se usó. Nadie la edita a mano.
"""

from django.core.exceptions import ValidationError
from django.db import models

from apps.tenancy.models import TenantScopedModel


class Asset(TenantScopedModel):
    """Activo del inventario. Es también donde se apoyan los componentes de seguridad (§7.2)."""

    system = models.ForeignKey(
        "compliance.System", on_delete=models.CASCADE, related_name="activos"
    )
    asset_type = models.ForeignKey(
        "catalog.MageritAssetType", on_delete=models.PROTECT, related_name="activos"
    )
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    responsable = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="activos"
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(fields=["system", "nombre"], name="uniq_activo_por_sistema")
        ]
        verbose_name = "activo"
        verbose_name_plural = "activos"

    def __str__(self) -> str:
        return self.nombre


class AssetValuation(models.Model):
    """Valor propio del activo en una dimensión, de 0 a 10 (MAGERIT).

    Solo los activos terminales (información y servicios) deberían tener valor propio;
    el resto lo hereda por dependencias. No se impone: un cliente puede valorar lo que
    quiera, y la propagación se queda con el mayor de los dos.
    """

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="valoraciones")
    dim = models.CharField(
        max_length=1, choices=[("C", "C"), ("I", "I"), ("T", "T"), ("A", "A"), ("D", "D")]
    )
    own_value = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    justificacion = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["asset", "dim"], name="uniq_valoracion_activo_dim"),
            models.CheckConstraint(
                condition=models.Q(own_value__gte=0) & models.Q(own_value__lte=10),
                name="valor_de_activo_entre_0_y_10",
            ),
        ]
        verbose_name = "valoración de activo"
        verbose_name_plural = "valoraciones de activos"

    def __str__(self) -> str:
        return f"{self.asset} · {self.dim} = {self.own_value}"


class AssetDependency(models.Model):
    """`parent` depende de `child` en un grado de 0 a 1. El valor desciende por aquí.

    El grafo tiene que ser acíclico: el ciclo se detecta al recalcular
    (`engines.risk_engine.CicloDetectado`) y se le devuelve al cliente con los activos
    implicados, porque es un error de modelado suyo, no un fallo del sistema.
    """

    parent = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="depende_de")
    child = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="soporta")
    degree = models.DecimalField(max_digits=4, decimal_places=3, default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["parent", "child"], name="uniq_dependencia"),
            models.CheckConstraint(
                condition=~models.Q(parent=models.F("child")), name="dependencia_no_refleja"
            ),
            models.CheckConstraint(
                condition=models.Q(degree__gt=0) & models.Q(degree__lte=1),
                name="grado_de_dependencia_entre_0_y_1",
            ),
        ]
        verbose_name = "dependencia"
        verbose_name_plural = "dependencias"

    def __str__(self) -> str:
        return f"{self.parent} → {self.child} ({self.degree})"

    def clean(self) -> None:
        if self.parent_id and self.child_id and self.parent_id == self.child_id:
            raise ValidationError("Un activo no puede depender de sí mismo.")
        if self.parent_id and self.child_id and self.parent.system_id != self.child.system_id:
            raise ValidationError("Los dos activos tienen que ser del mismo sistema.")


class ThreatInstance(TenantScopedModel):
    """Una amenaza concreta sobre un activo y una dimensión.

    Nace con los valores por defecto del catálogo (`MageritThreatDefault`) y el cliente
    los ajusta: el análisis vale por ese ajuste, no por el punto de partida.
    """

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="amenazas")
    threat = models.ForeignKey("catalog.MageritThreat", on_delete=models.PROTECT)
    dim = models.CharField(max_length=1)
    #: Veces al año.
    frequency = models.DecimalField(max_digits=7, decimal_places=3)
    #: Proporción del valor que se pierde si ocurre (0..1).
    degradation = models.DecimalField(max_digits=4, decimal_places=3)
    notas = models.TextField(blank=True)

    class Meta:
        ordering = ["asset__nombre", "threat__orden", "dim"]
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "threat", "dim"], name="uniq_amenaza_por_activo_dim"
            ),
            models.CheckConstraint(
                condition=models.Q(degradation__gte=0) & models.Q(degradation__lte=1),
                name="degradacion_entre_0_y_1",
            ),
            models.CheckConstraint(
                condition=models.Q(frequency__gte=0), name="frecuencia_no_negativa"
            ),
        ]
        verbose_name = "amenaza sobre activo"
        verbose_name_plural = "amenazas sobre activos"

    def __str__(self) -> str:
        return f"{self.asset} · {self.threat.code} ({self.dim})"


class RiskResult(models.Model):
    """Foto del último cálculo para una instancia de amenaza. No se edita a mano."""

    threat_instance = models.OneToOneField(
        ThreatInstance, on_delete=models.CASCADE, related_name="resultado"
    )
    accumulated_value = models.DecimalField(max_digits=8, decimal_places=4)
    intrinsic_risk = models.DecimalField(max_digits=12, decimal_places=4)
    residual_freq_factor = models.DecimalField(max_digits=8, decimal_places=6)
    residual_impact_factor = models.DecimalField(max_digits=8, decimal_places=6)
    residual_risk = models.DecimalField(max_digits=12, decimal_places=4)
    #: Qué medidas y con qué madurez produjeron esos factores: es la traza del informe.
    salvaguardas = models.JSONField(default=list, blank=True)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-residual_risk"]
        verbose_name = "resultado de riesgo"
        verbose_name_plural = "resultados de riesgo"

    def __str__(self) -> str:
        return f"{self.threat_instance} · residual {self.residual_risk}"


class Decision(models.TextChoices):
    MITIGAR = "MITIGAR", "Reducir"
    ACEPTAR = "ACEPTAR", "Aceptar"
    TRANSFERIR = "TRANSFERIR", "Transferir"
    EVITAR = "EVITAR", "Evitar"


class RiskTreatment(TenantScopedModel):
    """Qué se decide hacer con un riesgo. **Sin preselección**: arranca sin decidir.

    Aceptar un riesgo alto es una decisión de dirección, no un valor por defecto: por eso
    no existe aquí ninguna decisión implícita y `riesgo_aceptar` es una acción propia del
    RSEG y de dirección en la matriz de permisos.
    """

    threat_instance = models.OneToOneField(
        ThreatInstance, on_delete=models.CASCADE, related_name="tratamiento"
    )
    decision = models.CharField(max_length=12, choices=Decision.choices, blank=True)
    target_risk = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    owner = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="riesgos_a_cargo",
    )
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    #: Quién aceptó el riesgo y cuándo. Solo se rellena al aceptar (queda registrado).
    aceptado_por = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="riesgos_aceptados",
    )
    aceptado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "tratamiento del riesgo"
        verbose_name_plural = "tratamientos del riesgo"

    def __str__(self) -> str:
        return f"{self.threat_instance} · {self.get_decision_display() or 'sin decidir'}"
