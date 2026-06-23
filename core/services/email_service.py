import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import escape


logger = logging.getLogger(__name__)


def enviar_email_contato(nome: str, telefone: str, email: str, assunto: str):
    """
    Envia e-mail de contato via SMTP configurado no Django.
    """
    subject = "contato realizado via meu portifolio"
    from_email = settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER
    recipient_list = [settings.CONTACT_EMAIL or settings.EMAIL_HOST_USER]

    corpo_texto = (
        f"Nome: {nome}\n"
        f"Telefone: {telefone}\n"
        f"E-mail: {email}\n"
        f"Assunto: {assunto}"
    )
    nome_html = escape(nome)
    telefone_html = escape(telefone)
    email_html = escape(email)
    assunto_html = escape(assunto)
    corpo_html = (
        f"<p><strong>Nome:</strong> {nome_html}<br>"
        f"<strong>Telefone:</strong> {telefone_html}<br>"
        f"<strong>E-mail:</strong> {email_html}<br>"
        f"<strong>Assunto:</strong> {assunto_html}</p>"
    )

    try:
        message = EmailMultiAlternatives(
            subject=subject,
            body=corpo_texto,
            from_email=from_email,
            to=recipient_list,
            reply_to=[email],
        )
        message.attach_alternative(corpo_html, "text/html")
        response = message.send(fail_silently=False)
        logger.info(
            "Contato enviado via SMTP",
            extra={"to": recipient_list[0], "from": from_email},
        )
        return response
    except Exception:
        logger.exception("Falha ao enviar email de contato via SMTP")
        raise
