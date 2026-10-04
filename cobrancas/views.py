import hmac
import logging

import requests
from django.conf import settings
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .asaas import AsaasError
from .billing import confirmar_pagamento, estado_cobranca, garantir_cobranca_pix
from .models import AssinaturaSistema, EventoWebhookAsaas

logger = logging.getLogger(__name__)


def _autorizado(request):
    token = settings.COBRANCA_MARMITARIA_TOKEN
    return bool(token and hmac.compare_digest(token, request.headers.get("X-Cobranca-Token", "")))


def _serializar(estado, pix=None):
    assinatura = estado["assinatura"]
    return {
        **{key: value for key, value in estado.items() if key != "assinatura"},
        "assinatura": {
            "vencimento_atual": assinatura.vencimento_atual.isoformat(),
            "dia_vencimento": assinatura.dia_vencimento,
            "valor": str(assinatura.valor),
            "pix_copia_cola": assinatura.pix_copia_cola,
        } if assinatura else None,
        "pix": pix,
    }


@require_GET
def estado_marmitaria(request):
    if not _autorizado(request):
        return HttpResponseForbidden("Consulta não autorizada.")
    if not settings.COBRANCA_AUTOMATICA_ENABLED:
        return JsonResponse(_serializar(estado_cobranca()))
    if not estado_cobranca()["habilitada"]:
        return JsonResponse({"detail": "Cobrança central não configurada."}, status=503)
    pix = None
    if request.path.endswith("/pix/"):
        try:
            _, pix = garantir_cobranca_pix()
        except (AsaasError, requests.RequestException):
            logger.exception("Falha ao consultar Pix da marmitaria no Asaas.")
            return JsonResponse({"detail": "Pix indisponível temporariamente."}, status=503)
    response = JsonResponse(_serializar(estado_cobranca(), pix))
    response["Cache-Control"] = "no-store"
    return response


@csrf_exempt
@require_POST
def webhook_asaas(request):
    token_configurado = settings.ASAAS_WEBHOOK_TOKEN
    token_recebido = request.headers.get("asaas-access-token", "")
    if not token_configurado or not hmac.compare_digest(token_configurado, token_recebido):
        return HttpResponseForbidden("Webhook não autorizado.")

    try:
        payload = request.json if hasattr(request, "json") else None
        if payload is None:
            import json
            payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"detail": "JSON inválido."}, status=400)

    if not isinstance(payload, dict) or not isinstance(payload.get("payment", {}), dict):
        return JsonResponse({"detail": "Evento inválido."}, status=400)

    event_id = str(payload.get("id", "")).strip()
    event_type = str(payload.get("event", "")).strip()
    payment = payload.get("payment") or {}
    payment_id = str(payment.get("id", "")).strip()

    if not event_id:
        return JsonResponse({"detail": "Evento sem id."}, status=400)

    if event_type in {"PAYMENT_RECEIVED", "PAYMENT_CONFIRMED"} and not payment_id:
        return JsonResponse({"detail": "Evento sem cobrança."}, status=400)

    # Event recording and payment confirmation either both commit or both roll
    # back, allowing Asaas to redeliver after a temporary failure.
    with transaction.atomic():
        evento, criado = EventoWebhookAsaas.objects.get_or_create(
            event_id=event_id, defaults={"event_type": event_type, "payload": payload},
        )
        if not criado:
            return JsonResponse({"ok": True, "duplicate": True})
        if event_type in {"PAYMENT_RECEIVED", "PAYMENT_CONFIRMED"}:
            confirmado = confirmar_pagamento(payment_id)
            if not confirmado:
                assinatura = AssinaturaSistema.objects.filter(pk=1).first()
                referencia = f"marmitaria-adriana-{assinatura.vencimento_atual.isoformat()}" if assinatura else None
                if referencia and payment.get("externalReference") == referencia:
                    # The event may arrive before the emission response is saved.
                    transaction.set_rollback(True)
                    return JsonResponse({"detail": "Cobrança aguardando associação; reenvie o evento."}, status=503)
    return JsonResponse({"ok": True})
