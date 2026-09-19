from django.contrib import admin

from apps.catalog.models import CatalogVersion, EnsMeasure, EnsRefuerzo, EnsRequirementItem


@admin.register(CatalogVersion)
class CatalogVersionAdmin(admin.ModelAdmin):
    list_display = ("code", "oscal_version", "source_version", "is_current", "published_at")


@admin.register(EnsMeasure)
class EnsMeasureAdmin(admin.ModelAdmin):
    list_display = ("code", "nombre", "marco", "familia", "aplicacion_por")
    list_filter = ("marco", "familia", "aplicacion_por")
    search_fields = ("code", "nombre")


@admin.register(EnsRefuerzo)
class EnsRefuerzoAdmin(admin.ModelAdmin):
    list_display = ("code", "titulo", "opcional")
    list_filter = ("opcional",)
    search_fields = ("code", "titulo")


@admin.register(EnsRequirementItem)
class EnsRequirementItemAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "measure")
    search_fields = ("code", "label", "prose")
