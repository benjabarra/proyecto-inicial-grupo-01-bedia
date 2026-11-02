from django.conf import settings
from django.db import models


class Categoria(models.Model):
    nombre = models.CharField(max_length=60, unique=True)

    class Meta:
        verbose_name_plural = "categorías"

    def __str__(self):
        return self.nombre


class Reporte(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        EN_REVISION = "en_revision", "En revisión"
        EN_PROCESO = "en_proceso", "En proceso"
        RESUELTO = "resuelto", "Resuelto"
        RECHAZADO = "rechazado", "Rechazado"

    titulo = models.CharField(max_length=120)
    descripcion = models.TextField()
    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name="reportes"
    )
    ubicacion = models.CharField(
        max_length=150, help_text="Edificio, sala o zona del campus"
    )
    foto = models.ImageField(upload_to="reportes/%Y/%m/", blank=True)
    latitud = models.FloatField(null=True, blank=True)
    longitud = models.FloatField(null=True, blank=True)
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.PENDIENTE
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reportes"
    )
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return f"{self.titulo} ({self.get_estado_display()})"