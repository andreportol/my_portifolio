import logging
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
            return render(request, 'contato_enviado.html')
        except ValueError as exc:
            logger.warning("Configuração de email ausente para envio de contato: %s", exc)
            mensagem = {
                'message': 'Erro de configuração no envio de e-mail. Por favor, tente novamente mais tarde.'
            }
            return render(request, 'erro_formulario_contato.html', mensagem)
        except Exception as exc:
            logger.exception("Erro ao enviar email de contato via Resend")
            mensagem = {
                'message': 'Erro ao enviar o email. Por favor, tente novamente mais tarde.'
            }
            return render(request, 'erro_formulario_contato.html', mensagem)

    # Se não for válido, volta para o formulário exibindo erros
    return render(request, 'contato.html', {'form': contatoform})
            
