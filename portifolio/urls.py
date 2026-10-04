from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('cobrancas/', include('cobrancas.urls')),
    path('', include('core.urls'))
]
