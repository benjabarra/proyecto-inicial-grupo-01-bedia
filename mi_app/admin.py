from django.contrib import admin
from .models import Campus, Categoria, Edificio, Perfil, Reporte, Sala, Universidad


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre",)


@admin.register(Reporte)
class ReporteAdmin(admin.ModelAdmin):
    list_display = ("titulo", "categoria", "estado", "autor", "creado")
    list_editable = ("estado",)  # cambiar el estado desde la lista
    list_filter = ("estado", "categoria", "sala__edificio")
    search_fields = ("titulo", "descripcion", "ubicacion")
    autocomplete_fields = ("sala",)


@admin.register(Universidad)
class UniversidadAdmin(admin.ModelAdmin):
    list_display = ("sigla", "nombre", "dominio", "activa")
    list_editable = ("activa",)


@admin.register(Campus)
class CampusAdmin(admin.ModelAdmin):
    list_display = ("nombre", "universidad", "ciudad", "activo", "orden")
    list_editable = ("activo", "orden")
    list_filter = ("universidad", "activo")


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ("usuario", "rol", "universidad", "campus", "activo")
    list_editable = ("rol",)  # aqui se nombra a un encargado
    list_filter = ("rol", "universidad")
    search_fields = ("usuario__username", "usuario__first_name")
    exclude = ("codigo", "codigo_creado", "intentos")

    @admin.display(boolean=True, description="Correo confirmado")
    def activo(self, perfil):
        return perfil.usuario.is_active


@admin.register(Edificio)
class EdificioAdmin(admin.ModelAdmin):
    list_display = ("letra", "nombre", "pisos")


@admin.register(Sala)
class SalaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "edificio", "piso", "tipo")
    list_filter = ("edificio", "piso", "tipo")
    search_fields = ("nombre",)
