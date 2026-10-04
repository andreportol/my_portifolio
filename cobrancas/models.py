from decimal import Decimal

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone

class TimeStampedModel(models.Model):
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="atualizado em")

    class Meta:
        abstract = True


class AssinaturaSistema(TimeStampedModel):
    vencimento_atual = models.DateField("vencimento atual")
    dia_vencimento = models.PositiveSmallIntegerField("dia contratado", validators=[MinValueValidator(1), MaxValueValidator(31)])
    emissao_pendente = models.BooleanField(default=False, help_text="Emissão iniciada: reconcilie com o Asaas antes de limpar este campo.")
    valor = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    asaas_payment_id = models.CharField(max_length=80, blank=True)
    pix_copia_cola = models.TextField(blank=True)
    pix_expira_em = models.DateTimeField(null=True, blank=True)
    lembrete_enviado_em = models.DateTimeField(null=True, blank=True)
    pago_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "assinatura do sistema"
        verbose_name_plural = "assinatura do sistema"

    def __str__(self):
        return f"Assinatura - vencimento {self.vencimento_atual:%d/%m/%Y}"

    @property
    def esta_pago(self):
        return bool(self.pago_em)


class EventoWebhookAsaas(models.Model):
    event_id = models.CharField(max_length=120, unique=True)
    event_type = models.CharField(max_length=80)
    recebido_em = models.DateTimeField(default=timezone.now)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "evento webhook Asaas"
        verbose_name_plural = "eventos webhook Asaas"
        ordering = ("-recebido_em",)

    def __str__(self):
        return f"{self.event_type} - {self.event_id}"
