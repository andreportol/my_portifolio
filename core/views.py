import logging
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.generic import TemplateView

from .forms import ContatoForms
from .services.email_service import enviar_email_contato


logger = logging.getLogger(__name__)


class IndexTemplateView(TemplateView):
    template_name = 'index.html'

class BiografiaTemplateView(TemplateView):
    template_name = 'biografia.html'

class BiografiaContinuacaoTemplateView(TemplateView):
    template_name = 'biografia_continuacao.html'

class ProjetosTemplateView(TemplateView):
    template_name = 'projetos.html'

def receber_email(request):
    form = ContatoForms()
    return render(request, 'contato.html', {'form': form})
    
def enviar_email(request):
    if request.method != 'POST':
        return redirect('core:contato')

    contatoform = ContatoForms(request.POST) # cria uma instancia de ContatoForms para validar os campos do template
    if contatoform.is_valid():
        nome = contatoform.cleaned_data['nome']
        telefone = contatoform.cleaned_data['telefone']
        email = contatoform.cleaned_data['email']
        assunto = contatoform.cleaned_data['assunto']

        try:
            enviar_email_contato(nome, telefone, email, assunto)
            messages.success(request, "E-mail enviado com sucesso.")
            return redirect('core:contato')
        except ValueError as exc:
            logger.warning("Configuração de email ausente para envio de contato: %s", exc)
            messages.error(request, str(exc))
            return redirect('core:contato')
        except Exception as exc:
            logger.exception("Erro ao enviar email de contato via Resend")
            user_error = str(exc)
            if len(user_error) > 200:
                user_error = user_error[:200] + "..."
            messages.error(request, f"Erro ao enviar o e-mail: {user_error}")
            return redirect('core:contato')

    # Se não for válido, volta para o formulário exibindo erros
    return render(request, 'contato.html', {'form': contatoform})
            
