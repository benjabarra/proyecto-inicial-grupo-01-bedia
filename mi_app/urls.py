# direcciones de la app de reportes (todas empiezan con /reportes/)
from django.urls import path
from . import views

app_name = "reportes"

urlpatterns = [
    # lista de reportes
    path("", views.lista_reportes, name="lista"),
    # mapa del campus
    path("mapa/", views.mapa, name="mapa"),
    # apoyar o quitar apoyo a un reporte
    path("<int:pk>/apoyar/", views.apoyar, name="apoyar"),
    # el encargado cambia el estado y deja un comentario
    path("<int:pk>/estado/", views.cambiar_estado, name="cambiar_estado"),
    # reportes propios
    path("mis-reportes/", views.mis_reportes, name="mis_reportes"),
    # mi perfil
    path("perfil/", views.perfil, name="perfil"),
    # reporte nuevo
    path("nuevo/", views.crear_reporte, name="crear"),
    # detalle de un reporte
    path("<int:pk>/", views.detalle_reporte, name="detalle"),
]