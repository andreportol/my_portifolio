from django.urls import path

from .views import (BiografiaContinuacaoTemplateView, BiografiaTemplateView,
                    IndexTemplateView, ProjetosTemplateView, enviar_email,
                    receber_email)

app_name = 'core'

urlpatterns = [
    path('', IndexTemplateView.as_view(), name='index'),
    path('biografia/', BiografiaTemplateView.as_view(), name='biografia'),
    path('continuacao_biografia/', BiografiaContinuacaoTemplateView.as_view(), name='biografia_continuacao'),
    path('projetos/', ProjetosTemplateView.as_view(), name='projetos'),
    path('contato/', receber_email, name='contato'),
    path('enviar_email/', enviar_email, name='enviar_email'),
]
