import calendar
import logging
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

logger = logging.getLogger(__name__)


class _CobrancaNaoEncontrada(AsaasError):
    def __init__(self, assinatura):
        super().__init__("Cobrança associada não encontrada no Asaas.", status_code=404)
        self.payment_id = assinatura.asaas_payment_id
        self.referencia = assinatura.referencia_cobranca
        self.assinatura_id = assinatura.pk


def _reconciliar_cobranca_nao_encontrada(erro):
    client = AsaasClient()
    with transaction.atomic():
        assinatura = AssinaturaSistema.objects.select_for_update().get(pk=erro.assinatura_id)
        if (assinatura.asaas_payment_id != erro.payment_id
                or assinatura.referencia_cobranca != erro.referencia):
            return assinatura
        existente = client.buscar_cobranca(settings.ASAAS_CUSTOMER_ID, erro.referencia)
        if existente:
            if (not existente.get("id") or existente["id"] == erro.payment_id
                    or existente.get("customer") != settings.ASAAS_CUSTOMER_ID
                    or existente.get("billingType") != "PIX"
                    or existente.get("externalReference") != erro.referencia
                    or existente.get("deleted")
                    or existente.get("status") not in {"PENDING", "OVERDUE", "RECEIVED", "CONFIRMED"}
                    or Decimal(str(existente.get("value", 0))) != assinatura.valor_pix):
                raise AsaasError("Não foi possível reconciliar a cobrança pelo vencimento e valor da assinatura.")
        # Somente a listagem autenticada concluída permite substituir o ID.
        # Timeout, erro HTTP ou duplicidade preservam a cobrança e sua reserva.
        assinatura.asaas_payment_id = existente["id"] if existente else ""
        assinatura.pix_copia_cola = ""
        assinatura.pix_expira_em = None
        assinatura.lembrete_enviado_em = None
        assinatura.emissao_pendente = False
        assinatura.save(update_fields=["asaas_payment_id", "pix_copia_cola", "pix_expira_em",
            "lembrete_enviado_em", "emissao_pendente", "atualizado_em"])
        logger.warning("Referência da mensalidade reconciliada após cobrança não encontrada no Asaas.")
        if existente and existente["status"] in {"RECEIVED", "CONFIRMED"}:
            confirmar_pagamento(assinatura.asaas_payment_id)
            assinatura.refresh_from_db()
            return assinatura
    return None


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
    try:
        return _garantir_cobranca_pix()
    except _CobrancaNaoEncontrada as exc:
        # A transação da consulta já terminou: reconciliar antes de uma única
        # nova tentativa, mantendo a reserva de emissão contra duplicações.
        resolvida = _reconciliar_cobranca_nao_encontrada(exc)
        if resolvida:
            return resolvida, None
        return _garantir_cobranca_pix()


def _garantir_cobranca_pix():
    assinatura = obter_assinatura()
    if not assinatura:
        return None, None
    client = AsaasClient()
    criar = False
    recebida = False
    hoje = timezone.localdate(timezone=ZoneInfo(settings.COBRANCA_TIME_ZONE))
    # Persist the reservation before contacting Asaas. A lost response must
    # only trigger reconciliation, never a second POST for this cycle.
    with transaction.atomic():
        assinatura = AssinaturaSistema.objects.select_for_update().get(pk=assinatura.pk)
        referencia = assinatura.referencia_cobranca
        if not assinatura.asaas_payment_id:
            existente = client.buscar_cobranca(settings.ASAAS_CUSTOMER_ID, referencia)
            if (not existente and not assinatura.emissao_pendente
                    and hoje > (assinatura.vencimento_pix or assinatura.vencimento_atual)):
                assinatura.vencimento_pix = hoje
                referencia = assinatura.referencia_cobranca
                existente = client.buscar_cobranca(settings.ASAAS_CUSTOMER_ID, referencia)
            if existente:
                if Decimal(str(existente["value"])) != assinatura.valor_pix:
                    raise AsaasError("Valor da cobrança existente diverge da assinatura. Reconcilie no Asaas.")
                recebida = existente.get("status") in {"RECEIVED", "CONFIRMED"}
                assinatura.asaas_payment_id = existente["id"]
                assinatura.emissao_pendente = False
                assinatura.save(update_fields=["asaas_payment_id", "vencimento_pix", "emissao_pendente", "atualizado_em"])
            elif assinatura.emissao_pendente:
                raise AsaasError("Emissão aguardando reconciliação no Asaas; nova cobrança não será criada.")
            else:
                assinatura.emissao_pendente = True
                assinatura.save(update_fields=["vencimento_pix", "emissao_pendente", "atualizado_em"])
                criar = True
    if recebida:
        confirmar_pagamento(assinatura.asaas_payment_id)
        assinatura.refresh_from_db()
        return assinatura, None
    renovar = False
    if assinatura.asaas_payment_id and hoje > (assinatura.vencimento_pix or assinatura.vencimento_atual):
        with transaction.atomic():
            atual = AssinaturaSistema.objects.select_for_update().get(pk=assinatura.pk)
            if atual.asaas_payment_id and hoje > (atual.vencimento_pix or atual.vencimento_atual):
                try:
                    antiga = client.obter_cobranca(atual.asaas_payment_id)
                except AsaasError as exc:
                    if exc.status_code == 404:
                        raise _CobrancaNaoEncontrada(atual) from exc
                    raise
                if (antiga.get('customer') != settings.ASAAS_CUSTOMER_ID
                        or antiga.get('billingType') != 'PIX'):
                    raise AsaasError('Cobrança antiga não pertence à assinatura Pix.')
                if antiga.get('status') in {'RECEIVED', 'CONFIRMED'}:
                    confirmar_pagamento(atual.asaas_payment_id)
                    atual.refresh_from_db()
                    return atual, None
                if not antiga.get('deleted'):
                    if antiga.get('status') not in {'PENDING', 'OVERDUE'}:
                        raise AsaasError('Cobrança antiga indisponível para substituição.')
                    client.excluir_cobranca(atual.asaas_payment_id)
                atual.asaas_payment_id = ''
                atual.pix_copia_cola = ''
                atual.pix_expira_em = None
                atual.lembrete_enviado_em = None
                atual.vencimento_pix = hoje
                atual.emissao_pendente = False
                atual.save(update_fields=['asaas_payment_id', 'pix_copia_cola', 'pix_expira_em',
                    'lembrete_enviado_em', 'vencimento_pix', 'emissao_pendente', 'atualizado_em'])
                renovar = True
        if renovar:
            return _garantir_cobranca_pix()
    if criar:
        try:
            cobranca = client.criar_cobranca_pix(
                customer_id=settings.ASAAS_CUSTOMER_ID, value=assinatura.valor_pix,
                due_date=assinatura.vencimento_pix or assinatura.vencimento_atual,
                description=settings.COBRANCA_DESCRICAO + (' (acréscimo único de 5% por atraso)' if assinatura.vencimento_pix else ''),
                external_reference=referencia,
            )
        except AsaasError as exc:
            if exc.emissao_rejeitada:
                # A validação recusou o POST: não existe emissão para reconciliar.
                # Não limpar reservas de outro ciclo ou cobranças já associadas.
                AssinaturaSistema.objects.filter(
                    pk=assinatura.pk, vencimento_atual=assinatura.vencimento_atual,
                    vencimento_pix=assinatura.vencimento_pix,
                    asaas_payment_id="", emissao_pendente=True,
                ).update(emissao_pendente=False, atualizado_em=timezone.now())
            raise
        with transaction.atomic():
            atual = AssinaturaSistema.objects.select_for_update().get(pk=assinatura.pk)
            if atual.referencia_cobranca != referencia:
                raise AsaasError("Vencimento alterado durante a emissão. Reconcilie no Asaas.")
            atual.asaas_payment_id = cobranca["id"]
            atual.emissao_pendente = False
            atual.save(update_fields=["asaas_payment_id", "emissao_pendente", "atualizado_em"])
            assinatura = atual
    payment_id = assinatura.asaas_payment_id
    try:
        pix = client.obter_pix(payment_id)
    except AsaasError as exc:
        if exc.status_code == 404 and not criar:
            # Um QR ainda indisponível não significa que a cobrança sumiu.
            # Confirme o 404 no pagamento antes de permitir a reconciliação.
            try:
                client.obter_cobranca(payment_id)
            except AsaasError as consulta:
                if consulta.status_code == 404:
                    raise _CobrancaNaoEncontrada(assinatura) from consulta
                raise
        raise
    # Do not restore an old payment ID if a webhook confirmed it meanwhile.
    AssinaturaSistema.objects.filter(pk=assinatura.pk, asaas_payment_id=assinatura.asaas_payment_id).update(
        pix_copia_cola=pix.get("payload", ""),
        pix_expira_em=parse_datetime(pix["expirationDate"]) if pix.get("expirationDate") else None,
    )
    assinatura.refresh_from_db()
    if assinatura.asaas_payment_id != payment_id:
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
        f"Valor: R$ {assinatura.valor_pix:.2f}\n"
        + ('Inclui acréscimo único de 5% por atraso.\n' if assinatura.vencimento_pix else '') + '\n'
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
    assinatura.vencimento_pix = None
    assinatura.emissao_pendente = False
    assinatura.save(update_fields=["pago_em","vencimento_atual","asaas_payment_id","pix_copia_cola","pix_expira_em","lembrete_enviado_em","vencimento_pix","emissao_pendente","atualizado_em"])
    return True
