from django.contrib import admin

from apps.tenancy.models import AuditLog, Invitation, Membership, Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("nombre", "cif", "creado_en")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "tenant", "role", "estado", "expires_at")
    list_filter = ("role", "estado")


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "tenant", "role", "expires_at", "used_at")
    readonly_fields = ("token_hash",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Append-only: se consulta, no se toca."""

    list_display = ("created_at", "tenant", "user", "accion", "objeto_tipo", "objeto_id")
    list_filter = ("accion",)

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
