"""Perfilado del sistema (M11): lo que el cliente cuenta y lo que de ahí se deduce.

Es el eje del producto (§10bis): a través de preguntas en castellano llano, BLENS aprende
cómo es el sistema y con eso arma la carpeta de evidencias a medida. Aquí viven las
**respuestas** y los **hechos**; las preguntas son catálogo (`apps.catalog`) y las reglas
las evalúa `engines.evidence_engine`.

Tres cosas que este modelo hace a propósito:

- **La respuesta y el hecho van separados.** Una respuesta es lo que dijo una persona un
  día; un hecho es lo que el motor consume. Cambiar la redacción de una opción no reescribe
  el historial, y un hecho siempre sabe de qué respuesta salió (trazabilidad, §10bis.4).
- **El historial no se pisa.** Cada cambio de respuesta deja la anterior guardada: el
  auditor pregunta «¿desde cuándo?» y la respuesta no puede ser «desde que lo cambiamos».
- **«No lo sé» no es una opción del menú** (§4 M11): es delegar la pregunta a quien la
  sepa, y eso crea una tarea con nombre y apellidos.
"""

from __future__ import annotations

from django.db import models

from apps.tenancy.models import TenantScopedModel


class ProfileAnswer(TenantScopedModel):
    """La respuesta vigente a una pregunta del perfilado para un sistema."""

    system = models.ForeignKey(
        "compliance.System", on_delete=models.CASCADE, related_name="respuestas_perfilado"
    )
    question = models.ForeignKey(
        "catalog.ProfileQuestion", on_delete=models.PROTECT, related_name="respuestas"
    )
    #: El valor crudo, con la forma que pida el tipo de pregunta (código, lista, tabla…).
    #: Traducirlo a hechos es cosa del motor, no de la vista.
    value = models.JSONField(null=True, blank=True)
    respondido_por = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    fecha = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["question__bloque__orden", "question__orden"]
        constraints = [
            models.UniqueConstraint(
                fields=["system", "question"], name="uniq_respuesta_por_pregunta"
            )
        ]
        verbose_name = "respuesta de perfilado"
        verbose_name_plural = "respuestas de perfilado"

    def __str__(self) -> str:
        return f"{self.system_id}/{self.question.code}"

    @property
    def bloque(self) -> str:
        """El bloque al que pertenece. `can()` lo usa para acotar al COLABORADOR."""
        return self.question.bloque.code if self.question.bloque_id else ""


class ProfileAnswerHistory(models.Model):
    """Lo que se respondió antes. Solo se añade: nadie reescribe el pasado."""

    answer = models.ForeignKey(ProfileAnswer, on_delete=models.CASCADE, related_name="historial")
    value = models.JSONField(null=True, blank=True)
    respondido_por = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    fecha = models.DateTimeField()

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "respuesta anterior"
        verbose_name_plural = "historial de respuestas"

    def __str__(self) -> str:
        return f"{self.answer_id} @ {self.fecha:%Y-%m-%d}"


class ProfileFact(TenantScopedModel):
    """Un hecho del sistema: la entrada de `engines.evidence_engine`.

    La clave es **plana y en snake_case** (`instalacion_cpd`, `cred_ciclo`). No se usan
    puntos: en JSON Logic `{var: "hechos.a.b"}` significa recorrer `hechos → a → b`, así
    que un hecho llamado `a.b` no resolvería jamás.
    """

    system = models.ForeignKey("compliance.System", on_delete=models.CASCADE, related_name="hechos")
    key = models.CharField(max_length=60)
    value = models.JSONField(null=True, blank=True)
    source_answer = models.ForeignKey(
        ProfileAnswer, null=True, blank=True, on_delete=models.SET_NULL, related_name="hechos"
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]
        constraints = [
            models.UniqueConstraint(fields=["system", "key"], name="uniq_hecho_por_sistema")
        ]
        verbose_name = "hecho del sistema"
        verbose_name_plural = "hechos del sistema"

    def __str__(self) -> str:
        return f"{self.key} = {self.value!r}"


class EstadoDelegacion(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    RESUELTA = "RESUELTA", "Resuelta"
    CANCELADA = "CANCELADA", "Cancelada"


class ProfileDelegation(TenantScopedModel):
    """«Se lo pregunto a otra persona»: la alternativa honrada a un «no lo sé» del menú.

    Se mide la tasa por pregunta: por encima del 20 % la pregunta está mal redactada y se
    reescribe (§4 M11). Por eso la delegación se guarda aunque luego se resuelva.
    """

    system = models.ForeignKey(
        "compliance.System", on_delete=models.CASCADE, related_name="delegaciones_perfilado"
    )
    question = models.ForeignKey(
        "catalog.ProfileQuestion", on_delete=models.PROTECT, related_name="delegaciones"
    )
    asignado_a = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="preguntas_a_resolver",
    )
    #: Cuando quien lo sabe no tiene cuenta todavía: se invita o se le pregunta por fuera.
    asignado_email = models.EmailField(blank=True)
    creado_por = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    nota = models.TextField(blank=True)
    estado = models.CharField(
        max_length=10, choices=EstadoDelegacion.choices, default=EstadoDelegacion.PENDIENTE
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    resuelto_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "pregunta delegada"
        verbose_name_plural = "preguntas delegadas"

    def __str__(self) -> str:
        return f"{self.question.code} → {self.asignado_a or self.asignado_email}"

    @property
    def bloque(self) -> str:
        return self.question.bloque.code if self.question.bloque_id else ""
