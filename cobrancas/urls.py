from django.urls import path

from . import views

urlpatterns = [
    path("api/marmitaria/estado/", views.estado_marmitaria, name="estado_marmitaria"),
    path("api/marmitaria/pix/", views.estado_marmitaria, name="pix_marmitaria"),
    path("api/marmitaria/aviso-exibido/", views.registrar_aviso_exibido, name="registrar_aviso_exibido"),
    path("asaas/webhook/", views.webhook_asaas, name="webhook_asaas_central"),
]
