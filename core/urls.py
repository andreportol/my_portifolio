from django.urls import path

from .views import (
    BiografiaContinuacaoTemplateView,
    BiografiaTemplateView,
    IndexTemplateView,
    LicencaGestaoOficinaTemplateView,
    LicencaGestaoSalaoBelezaTemplateView,
    LicencasTemplateView,
    ProjetosTemplateView,
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
    path('contato/', receber_email, name='contato'),
    path('entrar/', entrar, name='entrar'),
    path('sair/', sair, name='sair'),
    path('licencas/', LicencasTemplateView.as_view(), name='licencas'),
    path(
        'licencas/gestao-oficina/',
        LicencaGestaoOficinaTemplateView.as_view(),
        name='licenca_gestao_oficina',
    ),
    path(
        'licencas/gestao-salao-beleza/',
        LicencaGestaoSalaoBelezaTemplateView.as_view(),
        name='licenca_gestao_salao_beleza',
    ),
    path('enviar_email/', enviar_email, name='enviar_email'),
]
