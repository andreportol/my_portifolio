import resend
from django.conf import settings
from django.shortcuts import render
from django.views.generic import TemplateView

from .forms import ContatoForms


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
    if request.method == 'POST':      
        contatoform = ContatoForms(request.POST) # cria uma instancia de ContatoForms para validar os campos do template
        if contatoform.is_valid():
            nome = contatoform.cleaned_data['nome']
            telefone = contatoform.cleaned_data['telefone']
            email = contatoform.cleaned_data['email']
            assunto = contatoform.cleaned_data['assunto']

            titulo = 'E-mail enviado através do portifólio.'

            if not settings.RESEND_API_KEY:
                mensagem = {
                    'message': 'Erro de configuração no envio de e-mail. Por favor, tente novamente mais tarde.'
                }
                return render(request, 'erro_formulario_contato.html', mensagem)

            corpo_html = (
                f"<p>Nome: {nome}<br>"
                f"Telefone: {telefone}<br>"
                f"E-mail: {email}<br>"
                f"Assunto: {assunto}</p>"
            )

            try:
                resend.api_key = settings.RESEND_API_KEY
                response = resend.Emails.send({
                    "from": settings.RESEND_FROM_EMAIL,
                    "to": ['andreportol@gmail.com'],
                    "subject":'MY PORTIFOLIO',
                    "html": "<strong>Email enviado com sucesso via Resend + Railway</strong>",
                    "reply_to": [email],
                })
                print(response)
                return render(request, 'contato_enviado.html')
            except Exception as e:
                print(str(e))
                mensagem = {
                    'message': 'Erro ao enviar o email. Por favor, tente novamente mais tarde.'
                }
                return render(request, 'erro_formulario_contato.html', mensagem)
        # Se não for válido, volta para o formulário exibindo erros
        return render(request, 'contato.html', {'form': contatoform})
            
