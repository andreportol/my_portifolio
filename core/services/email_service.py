import logging

import resend
from django.conf import settings


logger = logging.getLogger(__name__)


def enviar_email_contato(nome: str, telefone: str, email: str, assunto: str):
    """
    Envia e-mail de contato via Resend API com corpo contendo dados do formulário.
    """
    if not settings.RESEND_API_KEY:
        raise ValueError("RESEND_API_KEY não configurada.")

    resend.api_key = settings.RESEND_API_KEY

    subject = "E-mail enviado através do portifólio."
    corpo_html = (
        f"<p><strong>Nome:</strong> {nome}<br>"
        f"<strong>Telefone:</strong> {telefone}<br>"
        f"<strong>E-mail:</strong> {email}<br>"
        f"<strong>Assunto:</strong> {assunto}</p>"
    )

    payload = {
        "from": settings.RESEND_FROM_EMAIL or "onboarding@resend.dev",
        "to": [settings.CONTACT_EMAIL],
        "subject": subject,
        "html": corpo_html,
        "reply_to": email,
    }

    try:
        response = resend.Emails.send(payload)
        logger.info(
            "Contato enviado via Resend",
            extra={"to": settings.CONTACT_EMAIL, "from": settings.RESEND_FROM_EMAIL},
        )
        return response
    except Exception:
        logger.exception("Falha ao enviar email de contato via Resend")
        raise
