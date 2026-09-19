"""Sistemas de información bajo alcance.

En F0 solo existe `System`, porque la membresía necesita poder limitar su ámbito a
sistemas concretos. La categorización (M1), la DdA (M2) y la madurez (M4) llegan en
sus fases (docs/plan_construccion.md).
"""

from django.db import models

from apps.tenancy.models import TenantScopedModel


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
