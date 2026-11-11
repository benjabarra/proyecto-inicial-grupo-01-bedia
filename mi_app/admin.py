# panel de administracion: el encargado ve y edita todo desde /admin
from django.contrib import admin
from .models import Apoyo, Campus, Categoria, Edificio, Perfil, Reporte, Sala, Seguimiento, Universidad


# categorias de problemas
@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre",)


# historial del reporte dentro de su pagina en el admin (solo para leer)
class SeguimientoInline(admin.TabularInline):
    model = Seguimiento
    extra = 0
    can_delete = False
    fields = ("creado", "autor", "estado_anterior", "estado_nuevo", "comentario")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


# reportes: se puede cambiar el estado directo en la lista.
# cada cambio hecho aqui tambien queda en el historial del reporte
@admin.register(Reporte)
class ReporteAdmin(admin.ModelAdmin):
    list_display = ("titulo", "categoria", "estado", "autor", "creado")
    list_editable = ("estado",)  # cambiar el estado desde la lista
    list_filter = ("estado", "categoria", "sala__edificio")
    search_fields = ("titulo", "descripcion", "ubicacion")
    autocomplete_fields = ("sala",)
    inlines = [SeguimientoInline]

    def save_model(self, request, obj, form, change):
        anterior = Reporte.objects.filter(pk=obj.pk).values_list("estado", flat=True).first() if change else None
        super().save_model(request, obj, form, change)
        if anterior and anterior != obj.estado:
            Seguimiento.objects.create(
                reporte=obj, autor=request.user, estado_anterior=anterior,
                estado_nuevo=obj.estado, comentario="Cambiado desde la administración.",
            )


# historial de todos los reportes
@admin.register(Seguimiento)
class SeguimientoAdmin(admin.ModelAdmin):
    list_display = ("reporte", "estado_anterior", "estado_nuevo", "autor", "creado")
    list_filter = ("estado_nuevo",)
    search_fields = ("reporte__titulo", "comentario")


# universidades
@admin.register(Universidad)
class UniversidadAdmin(admin.ModelAdmin):
    list_display = ("sigla", "nombre", "dominio", "activa")
    list_editable = ("activa",)


# campus de cada universidad
@admin.register(Campus)
class CampusAdmin(admin.ModelAdmin):
    list_display = ("nombre", "universidad", "ciudad", "activo", "orden")
    list_editable = ("activo", "orden")
    list_filter = ("universidad", "activo")


# perfiles: aqui se nombra a un encargado cambiando su rol
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


# edificios
@admin.register(Edificio)
class EdificioAdmin(admin.ModelAdmin):
    list_display = ("letra", "nombre", "pisos")


# salas del mapa
@admin.register(Sala)
class SalaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "edificio", "piso", "tipo")
    list_filter = ("edificio", "piso", "tipo")
    search_fields = ("nombre",)


# apoyos: quien apoyo cada reporte
@admin.register(Apoyo)
class ApoyoAdmin(admin.ModelAdmin):
    list_display = ("reporte", "usuario", "creado")
    search_fields = ("reporte__titulo", "usuario__username")
