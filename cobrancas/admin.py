from django.contrib import admin

from .models import AssinaturaSistema, EventoWebhookAsaas


class AdminVendedor(admin.ModelAdmin):
    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AssinaturaSistema)
class AssinaturaSistemaAdmin(AdminVendedor):
    list_display = ("vencimento_atual", "dia_vencimento", "valor", "asaas_payment_id", "pago_em")
    readonly_fields = ("nome_projeto", "status_projeto", "asaas_payment_id", "emissao_pendente", "pix_copia_cola", "pix_expira_em", "lembrete_enviado_em", "pago_em", "criado_em", "atualizado_em")

    def has_add_permission(self, request):
        return super().has_add_permission(request) and not AssinaturaSistema.objects.exists()

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if obj and (obj.asaas_payment_id or obj.emissao_pendente):
            return fields + ("valor", "vencimento_atual", "dia_vencimento")
        return fields


@admin.register(EventoWebhookAsaas)
class EventoWebhookAsaasAdmin(AdminVendedor):
    list_display = ("event_type", "event_id", "recebido_em")
    readonly_fields = ("event_id", "event_type", "recebido_em", "payload")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
