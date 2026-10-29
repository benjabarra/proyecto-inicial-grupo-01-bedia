from django.contrib import admin
from .models import Categoria, Reporte


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre",)


@admin.register(Reporte)
class ReporteAdmin(admin.ModelAdmin):
    list_display = ("titulo", "categoria", "estado", "autor", "creado")
    list_filter = ("estado", "categoria")
    search_fields = ("titulo", "descripcion", "ubicacion")