from django.urls import path
from . import views

app_name = "reportes"

urlpatterns = [
    path("", views.lista_reportes, name="lista"),
    path("mis-reportes/", views.mis_reportes, name="mis_reportes"),
    path("nuevo/", views.crear_reporte, name="crear"),
    path("<int:pk>/", views.detalle_reporte, name="detalle"),
]