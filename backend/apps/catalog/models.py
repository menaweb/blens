"""Catálogo ENS: global, de solo lectura para los clientes y versionado.

Sale del **OSCAL oficial** (`db/seed/oscal`, sin editar) mediante `import_ens_oscal`.
Los ids OSCAL son la clave estable; nada se identifica de otra forma (§15).

La **aplicabilidad no se guarda**: se deriva con `engines.ens_applicability` a partir de
estas props más la categoría y los niveles del sistema (§7.1). Aquí solo se conserva lo
que dice el catálogo, tal cual.
"""

from decimal import Decimal

from django.db import models


class Marco(models.TextChoices):
    ORG = "org", "Marco organizativo"
    OP = "op", "Marco operacional"
    MP = "mp", "Medidas de protección"


class CatalogVersion(models.Model):
    """Una versión del catálogo. Los datos de tenant apuntan a la suya, no a «la última»."""

    code = models.CharField(max_length=60, unique=True)  # 'ENS-2022-OSCAL-1.0.0'
    published_at = models.DateTimeField(auto_now_add=True)
    is_current = models.BooleanField(default=False)

    oscal_version = models.CharField(max_length=20)
    source_version = models.CharField(max_length=40)
    source_last_modified = models.CharField(max_length=40, blank=True)
    source_url = models.URLField(blank=True)
    license = models.CharField(max_length=40, default="EUPL-1.2")
    #: Identifica el fichero exacto del que salió todo esto.
    source_sha256 = models.CharField(max_length=64)
    source_path = models.CharField(max_length=300, blank=True)
    #: Hueco para cuando el original viva en S3 con Object Lock (§11).
    source_s3_key = models.CharField(max_length=300, blank=True)
    #: Versión de la capa propia (checks, evidencias, mapas), que evoluciona aparte.
    blens_layer_version = models.CharField(max_length=40, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-published_at"]
        verbose_name = "versión del catálogo"
        verbose_name_plural = "versiones del catálogo"

    def __str__(self) -> str:
        return self.code

    @classmethod
    def current(cls) -> "CatalogVersion | None":
        return cls.objects.filter(is_current=True).first()


class EnsMeasure(models.Model):
    """Una de las 73 medidas del Anexo II."""

    catalog = models.ForeignKey(CatalogVersion, on_delete=models.CASCADE, related_name="measures")
    code = models.CharField(max_length=30)  # id OSCAL: 'op.exp.6'
    marco = models.CharField(max_length=5, choices=Marco.choices)
    familia = models.CharField(max_length=15)  # 'op.exp'
    nombre = models.CharField(max_length=300)
    overview = models.TextField(blank=True)

    aplicacion_por = models.CharField(max_length=20, blank=True)  # categoria | nivel-dimension
    categorias = models.JSONField(default=list, blank=True)
    niveles = models.JSONField(default=list, blank=True)
    dimensiones = models.JSONField(default=list, blank=True)  # códigos C/I/T/A/D
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["orden"]
        constraints = [
            models.UniqueConstraint(fields=["catalog", "code"], name="uniq_measure_por_catalogo")
        ]
        verbose_name = "medida"
        verbose_name_plural = "medidas"

    def __str__(self) -> str:
        return f"{self.code} · {self.nombre}"


class EnsRefuerzo(models.Model):
    """Refuerzo `<medida>.rN`. Sin props de aplicabilidad = opcional (§3.1)."""

    measure = models.ForeignKey(EnsMeasure, on_delete=models.CASCADE, related_name="refuerzos")
    code = models.CharField(max_length=30)  # 'op.exp.6.r1'
    titulo = models.CharField(max_length=300)

    aplicacion_por = models.CharField(max_length=20, blank=True)
    categorias = models.JSONField(default=list, blank=True)
    niveles = models.JSONField(default=list, blank=True)
    dimensiones = models.JSONField(default=list, blank=True)
    opcional = models.BooleanField(default=False)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["orden"]
        constraints = [
            models.UniqueConstraint(fields=["measure", "code"], name="uniq_refuerzo_por_medida")
        ]
        verbose_name = "refuerzo"
        verbose_name_plural = "refuerzos"

    def __str__(self) -> str:
        return self.code


class EnsSelectionParam(models.Model):
    """Disyunción «R1 o R2…»: la DdA no se aprueba sin resolverla (op.acc.5/6, mp.com.4, mp.s.2)."""

    measure = models.ForeignKey(EnsMeasure, on_delete=models.CASCADE, related_name="params")
    code = models.CharField(max_length=60)  # 'op.acc.5.prm.rfz.bajo'
    label = models.CharField(max_length=200, blank=True)
    usage = models.CharField(max_length=300, blank=True)
    categoria = models.CharField(max_length=10, blank=True)
    nivel = models.CharField(max_length=10, blank=True)
    choices = models.JSONField(default=list)  # ids de refuerzo; se elige UNO

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["measure", "code"], name="uniq_param_por_medida")
        ]
        verbose_name = "selección de refuerzo"
        verbose_name_plural = "selecciones de refuerzo"

    def __str__(self) -> str:
        return self.code


class EnsRequirementItem(models.Model):
    """Requisito atómico con su numeración literal. Es el ancla de checks y evidencias."""

    catalog = models.ForeignKey(CatalogVersion, on_delete=models.CASCADE, related_name="items")
    code = models.CharField(max_length=60)  # id OSCAL: 'op.exp.6.req.2'
    #: Numeración de la norma ('op.exp.6.2'). OJO: **no es única** entre medidas.
    label = models.CharField(max_length=40, blank=True)
    measure = models.ForeignKey(EnsMeasure, on_delete=models.CASCADE, related_name="items")
    refuerzo = models.ForeignKey(
        EnsRefuerzo, null=True, blank=True, on_delete=models.CASCADE, related_name="items"
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    prose = models.TextField(blank=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["orden"]
        constraints = [
            models.UniqueConstraint(fields=["catalog", "code"], name="uniq_item_por_catalogo")
        ]
        indexes = [models.Index(fields=["label"])]
        verbose_name = "requisito"
        verbose_name_plural = "requisitos"

    def __str__(self) -> str:
        return self.label or self.code


# --- Madurez y MAGERIT: la parte del catálogo que consumen los motores --------------


class MaturityEffectiveness(models.Model):
    """L0-L5 → eficacia de la salvaguarda (0..1). Configurable a propósito (§7.1).

    Es la bisagra entre el checklist y el análisis de riesgos: subir una medida de L2 a
    L3 cambia a la vez el índice de cumplimiento y el riesgo residual. Que sea una tabla
    y no una constante permite discutir la calibración con un consultor sin tocar código.
    """

    level = models.PositiveSmallIntegerField(primary_key=True)
    label = models.CharField(max_length=40)
    effectiveness = models.DecimalField(max_digits=4, decimal_places=3)

    class Meta:
        ordering = ["level"]
        verbose_name = "eficacia por madurez"
        verbose_name_plural = "eficacias por madurez"

    def __str__(self) -> str:
        return f"L{self.level} · {self.label} ({self.effectiveness})"

    @classmethod
    def tabla(cls) -> dict[int, Decimal]:
        """La tabla tal y como la esperan los motores."""
        return {fila.level: fila.effectiveness for fila in cls.objects.all()}


class MageritAssetType(models.Model):
    """Tipo de activo de MAGERIT v3. Los subtipos cuelgan del tipo por `parent`."""

    catalog = models.ForeignKey(
        CatalogVersion, on_delete=models.CASCADE, related_name="asset_types"
    )
    code = models.CharField(max_length=20)  # 'D', 'D.backup'
    name = models.CharField(max_length=200)
    #: True en información y servicios: es donde nace el valor y desde donde se propaga.
    is_terminal = models.BooleanField(default=False)
    ayuda = models.TextField(blank=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="subtipos"
    )
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["orden"]
        constraints = [
            models.UniqueConstraint(fields=["catalog", "code"], name="uniq_asset_type_por_catalogo")
        ]
        verbose_name = "tipo de activo"
        verbose_name_plural = "tipos de activo"

    def __str__(self) -> str:
        return f"[{self.code}] {self.name}"


class ThreatCategory(models.TextChoices):
    NATURAL = "NATURAL", "Desastres naturales"
    INDUSTRIAL = "INDUSTRIAL", "De origen industrial"
    ERROR = "ERROR", "Errores y fallos no intencionados"
    ATAQUE = "ATAQUE", "Ataques intencionados"


class MageritThreat(models.Model):
    """Amenaza del catálogo MAGERIT (Libro II)."""

    catalog = models.ForeignKey(CatalogVersion, on_delete=models.CASCADE, related_name="threats")
    code = models.CharField(max_length=10)  # 'A.24'
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=12, choices=ThreatCategory.choices)
    #: Dimensiones ACIDA que puede afectar.
    dims = models.JSONField(default=list)
    #: Tipos de activo donde tiene sentido proponerla (códigos de MageritAssetType).
    aplica_a = models.JSONField(default=list, blank=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["orden"]
        constraints = [
            models.UniqueConstraint(fields=["catalog", "code"], name="uniq_threat_por_catalogo")
        ]
        verbose_name = "amenaza"
        verbose_name_plural = "amenazas"

    def __str__(self) -> str:
        return f"[{self.code}] {self.name}"


class MageritThreatDefault(models.Model):
    """Punto de partida editable de frecuencia y degradación por dimensión.

    Son la primera calibración de BLENS, no cifras de MAGERIT: la metodología no fija
    números. El análisis vale por lo que el cliente ajusta, no por el valor por defecto.
    """

    threat = models.ForeignKey(
        MageritThreat, on_delete=models.CASCADE, related_name="valores_por_defecto"
    )
    dim = models.CharField(max_length=1)
    #: Proporción del valor que se pierde si ocurre (0..1).
    default_degradation = models.DecimalField(max_digits=4, decimal_places=3)
    #: Veces al año.
    default_frequency = models.DecimalField(max_digits=7, decimal_places=3)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["threat", "dim"], name="uniq_default_por_dimension")
        ]
        verbose_name = "valor por defecto de amenaza"
        verbose_name_plural = "valores por defecto de amenazas"

    def __str__(self) -> str:
        return f"{self.threat.code}/{self.dim}"


class Aspecto(models.TextChoices):
    FREQ = "FREQ", "Reduce la probabilidad"
    IMPACT = "IMPACT", "Reduce el daño"


class MeasureThreatMap(models.Model):
    """Qué medida del ENS frena qué amenaza y cuánto. Biblioteca curada por BLENS.

    Es el equivalente a la biblioteca de PILAR, y es criterio propio: los pesos están
    topados a 0,7 para que ninguna medida sola anule una amenaza (`measure_threat_map.yaml`).
    """

    catalog = models.ForeignKey(
        CatalogVersion, on_delete=models.CASCADE, related_name="measure_threat_map"
    )
    measure = models.ForeignKey(EnsMeasure, on_delete=models.CASCADE, related_name="salvaguarda_de")
    threat = models.ForeignKey(MageritThreat, on_delete=models.CASCADE, related_name="salvaguardas")
    #: Vacío = vale para todas las dimensiones de la amenaza.
    dim = models.CharField(max_length=1, blank=True)
    aspect = models.CharField(max_length=6, choices=Aspecto.choices)
    weight = models.DecimalField(max_digits=4, decimal_places=3)

    class Meta:
        ordering = ["threat__orden", "measure__orden"]
        constraints = [
            models.UniqueConstraint(
                fields=["catalog", "measure", "threat", "dim", "aspect"],
                name="uniq_salvaguarda",
            )
        ]
        verbose_name = "salvaguarda"
        verbose_name_plural = "mapa medida-amenaza"

    def __str__(self) -> str:
        return f"{self.measure.code} → {self.threat.code} ({self.aspect} {self.weight})"
