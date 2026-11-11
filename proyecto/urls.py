# direcciones principales del sitio
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from mi_app import views as vistas

urlpatterns = [
    # panel de administracion de django
    path("admin/", admin.site.urls),
    # cuentas: entrar, registro, verificar correo y salir
    path("cuentas/entrar/", vistas.entrar, name="login"),
    path("cuentas/registro/", vistas.registro, name="registro"),
    path("cuentas/verificar/", vistas.verificar, name="verificar"),
    path("cuentas/verificar/reenviar/", vistas.reenviar_codigo, name="reenviar_codigo"),
    path("cuentas/salir/", auth_views.LogoutView.as_view(), name="logout"),
    # todo lo de reportes y el mapa
    path("reportes/", include("mi_app.urls")),
    # portada
    path("", vistas.bienvenida, name="bienvenida"),
]

# en desarrollo, django muestra las fotos subidas
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
