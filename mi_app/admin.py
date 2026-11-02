from django.contrib import admin
from .models import Categoria, Perfil, Reporte, Universidad


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre",)


@admin.register(Reporte)
class ReporteAdmin(admin.ModelAdmin):
    list_display = ("titulo", "categoria", "estado", "autor", "creado")
    list_editable = ("estado",)  # cambiar el estado desde la lista
    list_filter = ("estado", "categoria")
    search_fields = ("titulo", "descripcion", "ubicacion")


@admin.register(Universidad)
class UniversidadAdmin(admin.ModelAdmin):
    list_display = ("sigla", "campus", "dominio")


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ("usuario", "rol", "universidad", "activo")
    list_editable = ("rol",)  # aqui se nombra a un encargado
    list_filter = ("rol", "universidad")
    search_fields = ("usuario__username", "usuario__first_name")
    exclude = ("codigo", "codigo_creado", "intentos")

    @admin.display(boolean=True, description="Correo confirmado")
    def activo(self, perfil):
        return perfil.usuario.is_active
