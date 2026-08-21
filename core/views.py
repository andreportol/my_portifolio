import logging
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import ContatoForms, LicencaGestaoOficinaForm, LoginForms
from .services.license_service import (
    gerar_codigo_licenca_gestao_oficina,
    gerar_codigo_licenca_gestao_salao_beleza,
)
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


class ProtectedTemplateView(LoginRequiredMixin, TemplateView):
    login_url = 'core:entrar'


class LicencasTemplateView(ProtectedTemplateView):
    template_name = 'licencas.html'


class LicencaSoftwaresTemplateView(ProtectedTemplateView):
    template_name = 'licenca_softwares.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault('form', LicencaGestaoOficinaForm())
        context.setdefault('codigo_gerado', '')
        return context

    def post(self, request, *args, **kwargs):
        form = LicencaGestaoOficinaForm(request.POST)
        codigo_gerado = ''
        if form.is_valid():
            try:
                codigo_gerado = gerar_codigo_licenca_gestao_oficina(
                    machine_id=form.cleaned_data['machine_id'],
                )
            except ValueError as exc:
                form.add_error(None, str(exc))
        context = self.get_context_data(form=form, codigo_gerado=codigo_gerado)
        return render(request, self.template_name, context)


class LicencaGestaoSalaoBelezaTemplateView(ProtectedTemplateView):
    template_name = 'licenca_gestao_salao_beleza.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault('form', LicencaGestaoOficinaForm())
        context.setdefault('codigo_gerado', '')
        return context

    def post(self, request, *args, **kwargs):
        form = LicencaGestaoOficinaForm(request.POST)
        codigo_gerado = ''
        if form.is_valid():
            try:
                codigo_gerado = gerar_codigo_licenca_gestao_salao_beleza(
                    machine_id=form.cleaned_data['machine_id'],
                )
            except ValueError as exc:
                form.add_error(None, str(exc))
        context = self.get_context_data(form=form, codigo_gerado=codigo_gerado)
        return render(request, self.template_name, context)


class PoliticaPrivacidadeTemplateView(TemplateView):
    template_name = 'politica_de_privacidade.html'


class TermosServicoTemplateView(TemplateView):
    template_name = 'termos_de_servico.html'

def receber_email(request):
    form = ContatoForms()
    return render(request, 'contato.html', {'form': form})


@require_http_methods(['GET', 'POST'])
def entrar(request):
    if request.user.is_authenticated:
        return redirect('core:licencas')

    form = LoginForms(request.POST or None)
    next_url = request.POST.get('next') or request.GET.get('next')
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        senha = form.cleaned_data['senha']
        user = authenticate(request, email=email, password=senha)
        if user is not None:
            auth_login(request, user)
            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect('core:licencas')
        form.add_error(None, 'E-mail ou senha inválidos.')

    return render(request, 'entrar.html', {'form': form, 'next': next_url})


@login_required(login_url='core:entrar')
def sair(request):
    auth_logout(request)
    return redirect('core:index')


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
            
