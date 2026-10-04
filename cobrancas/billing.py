import calendar
from datetime import date, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime


from .asaas import AsaasClient, AsaasError
from .models import AssinaturaSistema


def _proximo_mes(data, dia_contratado=None):
    ano = data.year + (1 if data.month == 12 else 0)
    mes = 1 if data.month == 12 else data.month + 1
    dia = min(dia_contratado or data.day, calendar.monthrange(ano, mes)[1])
    return date(ano, mes, dia)


def cobranca_habilitada():
    return bool(
        settings.COBRANCA_AUTOMATICA_ENABLED
        and settings.ASAAS_API_KEY
        and settings.ASAAS_CUSTOMER_ID
    )


def obter_assinatura():
    if not cobranca_habilitada():
        return None
    existente = AssinaturaSistema.objects.filter(pk=1).first()
    if existente:
        return existente
    vencimento = parse_date(settings.COBRANCA_PRIMEIRO_VENCIMENTO)
    if not vencimento or settings.COBRANCA_VALOR_MENSAL <= 0:
        return None
    assinatura, _ = AssinaturaSistema.objects.get_or_create(
        pk=1,
        defaults={"vencimento_atual": vencimento, "dia_vencimento": vencimento.day, "valor": settings.COBRANCA_VALOR_MENSAL},
    )
    return assinatura


def estado_cobranca(hoje=None):
    assinatura = obter_assinatura()
    if not assinatura:
        return {"habilitada": False, "gerente_bloqueado": False, "site_bloqueado": False, "assinatura": None, "dias_para_vencer": None, "mostrar_aviso": False}

    hoje = hoje or timezone.localdate(timezone=ZoneInfo(settings.COBRANCA_TIME_ZONE))
    vencimento = assinatura.vencimento_atual
    dias = (vencimento - hoje).days
    return {
        "habilitada": True,
        "gerente_bloqueado": hoje >= vencimento + timedelta(days=settings.COBRANCA_DIAS_BLOQUEIO_GERENTE),
        "site_bloqueado": hoje >= vencimento + timedelta(days=settings.COBRANCA_DIAS_BLOQUEIO_SITE),
        "assinatura": assinatura,
        "dias_para_vencer": dias,
        "mostrar_aviso": dias <= settings.COBRANCA_DIAS_ANTECEDENCIA,
    }


def _emails_gerentes():
    return [settings.COBRANCA_GERENTE_EMAIL] if settings.COBRANCA_GERENTE_EMAIL else []


def garantir_cobranca_pix():
    assinatura = obter_assinatura()
    if not assinatura:
        return None, None
    client = AsaasClient()
    criar = False
    recebida = False
    # Persist the reservation before contacting Asaas. A lost response must
    # only trigger reconciliation, never a second POST for this cycle.
    with transaction.atomic():
        assinatura = AssinaturaSistema.objects.select_for_update().get(pk=assinatura.pk)
        referencia = f"marmitaria-adriana-{assinatura.vencimento_atual.isoformat()}"
        if not assinatura.asaas_payment_id:
            existente = client.buscar_cobranca(settings.ASAAS_CUSTOMER_ID, referencia)
            if existente:
                if Decimal(str(existente["value"])) != assinatura.valor:
                    raise AsaasError("Valor da cobrança existente diverge da assinatura. Reconcilie no Asaas.")
                recebida = existente.get("status") in {"RECEIVED", "CONFIRMED"}
                assinatura.asaas_payment_id = existente["id"]
                assinatura.emissao_pendente = False
                assinatura.save(update_fields=["asaas_payment_id", "emissao_pendente", "atualizado_em"])
            elif assinatura.emissao_pendente:
                raise AsaasError("Emissão aguardando reconciliação no Asaas; nova cobrança não será criada.")
            else:
                assinatura.emissao_pendente = True
                assinatura.save(update_fields=["emissao_pendente", "atualizado_em"])
                criar = True
    if recebida:
        confirmar_pagamento(assinatura.asaas_payment_id)
        assinatura.refresh_from_db()
        return assinatura, None
    if criar:
        try:
            cobranca = client.criar_cobranca_pix(
                customer_id=settings.ASAAS_CUSTOMER_ID, value=assinatura.valor,
                due_date=assinatura.vencimento_atual, description=settings.COBRANCA_DESCRICAO,
                external_reference=referencia,
            )
        except AsaasError as exc:
            if exc.emissao_rejeitada:
                # A validação recusou o POST: não existe emissão para reconciliar.
                # Não limpar reservas de outro ciclo ou cobranças já associadas.
                AssinaturaSistema.objects.filter(
                    pk=assinatura.pk, vencimento_atual=assinatura.vencimento_atual,
                    asaas_payment_id="", emissao_pendente=True,
                ).update(emissao_pendente=False, atualizado_em=timezone.now())
            raise
        with transaction.atomic():
            atual = AssinaturaSistema.objects.select_for_update().get(pk=assinatura.pk)
            if atual.vencimento_atual != assinatura.vencimento_atual:
                raise AsaasError("Vencimento alterado durante a emissão. Reconcilie no Asaas.")
            atual.asaas_payment_id = cobranca["id"]
            atual.emissao_pendente = False
            atual.save(update_fields=["asaas_payment_id", "emissao_pendente", "atualizado_em"])
            assinatura = atual
    pix = client.obter_pix(assinatura.asaas_payment_id)
    # Do not restore an old payment ID if a webhook confirmed it meanwhile.
    AssinaturaSistema.objects.filter(pk=assinatura.pk, asaas_payment_id=assinatura.asaas_payment_id).update(
        pix_copia_cola=pix.get("payload", ""),
        pix_expira_em=parse_datetime(pix["expirationDate"]) if pix.get("expirationDate") else None,
    )
    assinatura.refresh_from_db()
    if not assinatura.asaas_payment_id:
        return assinatura, None
    return assinatura, pix


def preparar_e_enviar_cobranca():
    assinatura = obter_assinatura()
    if not assinatura:
        return "desabilitada"

    hoje = timezone.localdate(timezone=ZoneInfo(settings.COBRANCA_TIME_ZONE))
    data_lembrete = assinatura.vencimento_atual - timedelta(days=settings.COBRANCA_DIAS_ANTECEDENCIA)
    if hoje < data_lembrete:
        return "sem_acao"

    assinatura, pix = garantir_cobranca_pix()
    if not pix or assinatura.lembrete_enviado_em:
        return "sem_acao"
    destinatarios = _emails_gerentes()
    if not destinatarios:
        return "sem_email"

    vencimento = assinatura.vencimento_atual.strftime("%d/%m/%Y")
    mensagem = (
        f"Olá!\n\nA mensalidade do sistema da Marmitaria Adriana vence em {vencimento}.\n"
        f"Valor: R$ {assinatura.valor:.2f}\n\n"
        "Pix copia e cola:\n"
        f"{assinatura.pix_copia_cola}\n\n"
        "Você também pode pagar diretamente pelo painel do gerente.\n"
        "Após a confirmação do pagamento pelo Asaas, o sistema fará a liberação automaticamente.\n"
    )
    send_mail(
        subject=f"Mensalidade do sistema - vencimento {vencimento}",
        message=mensagem,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=destinatarios,
        fail_silently=False,
    )
    assinatura.lembrete_enviado_em = timezone.now()
    assinatura.save(update_fields=["lembrete_enviado_em", "atualizado_em"])
    return "enviada"


@transaction.atomic
def confirmar_pagamento(payment_id, payment_date=None):
    assinatura = AssinaturaSistema.objects.select_for_update().filter(asaas_payment_id=payment_id).first()
    if not assinatura:
        return False
    assinatura.pago_em = payment_date or timezone.now()
    assinatura.vencimento_atual = _proximo_mes(assinatura.vencimento_atual, assinatura.dia_vencimento)
    assinatura.asaas_payment_id = ""
    assinatura.pix_copia_cola = ""
    assinatura.pix_expira_em = None
    assinatura.lembrete_enviado_em = None
    assinatura.save(update_fields=["pago_em","vencimento_atual","asaas_payment_id","pix_copia_cola","pix_expira_em","lembrete_enviado_em","atualizado_em"])
    return True
