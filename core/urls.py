from django.urls import path
from django.views.generic import RedirectView

from .views import (
    BiografiaContinuacaoTemplateView,
    BiografiaTemplateView,
    IndexTemplateView,
    LicencaSoftwaresTemplateView,
    LicencaGestaoSalaoBelezaTemplateView,
    LicencasTemplateView,
    PoliticaPrivacidadeTemplateView,
    ProjetosTemplateView,
    TermosServicoTemplateView,
    entrar,
    enviar_email,
    receber_email,
    sair,
)

app_name = 'core'

urlpatterns = [
    path('', IndexTemplateView.as_view(), name='index'),
    path('biografia/', BiografiaTemplateView.as_view(), name='biografia'),
    path('continuacao_biografia/', BiografiaContinuacaoTemplateView.as_view(), name='biografia_continuacao'),
    path('projetos/', ProjetosTemplateView.as_view(), name='projetos'),
    path('politica-de-privacidade', PoliticaPrivacidadeTemplateView.as_view()),
    path('politica-de-privacidade/', PoliticaPrivacidadeTemplateView.as_view(), name='politica_privacidade'),
    path('termos-de-servico', TermosServicoTemplateView.as_view()),
    path('termos-de-servico/', TermosServicoTemplateView.as_view(), name='termos_servico'),
    path('contato/', receber_email, name='contato'),
    path('entrar/', entrar, name='entrar'),
    path('sair/', sair, name='sair'),
    path('licencas/', LicencasTemplateView.as_view(), name='licencas'),
    path(
        'licencas/softwares/',
        LicencaSoftwaresTemplateView.as_view(),
        name='licenca_softwares',
    ),
    path(
        'licencas/gestao-oficina/',
        RedirectView.as_view(pattern_name='core:licenca_softwares', permanent=True),
    ),
    path(
        'licencas/gestao-salao-beleza/',
        LicencaGestaoSalaoBelezaTemplateView.as_view(),
        name='licenca_gestao_salao_beleza',
    ),
    path('enviar_email/', enviar_email, name='enviar_email'),
]
