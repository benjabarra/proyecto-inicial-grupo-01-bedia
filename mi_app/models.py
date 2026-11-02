import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Categoria(models.Model):
    nombre = models.CharField(max_length=60, unique=True)

    class Meta:
        verbose_name_plural = "categorías"

    def __str__(self):
        return self.nombre


class Reporte(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        EN_PROCESO = "en_proceso", "En proceso"
        RESUELTO = "resuelto", "Resuelto"

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


class Universidad(models.Model):
    """datos de cada universidad: el tema de la pagina sale de aqui"""

    nombre = models.CharField(max_length=120)
    sigla = models.CharField(max_length=20)
    campus = models.CharField(max_length=80)
    dominio = models.CharField(max_length=100, unique=True)
    color_primario = models.CharField(max_length=7)
    color_acento = models.CharField(max_length=7)
    imagen = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name_plural = "universidades"

    def __str__(self):
        return f"{self.sigla} {self.campus}"


def universidad_para_correo(correo):
    """devuelve la universidad que corresponde al dominio del correo, o None"""
    if not correo or "@" not in correo:
        return None
    dominio = correo.rsplit("@", 1)[-1].strip().lower()
    for uni in Universidad.objects.all():
        if dominio == uni.dominio or dominio.endswith("." + uni.dominio):
            return uni
    return None


class Perfil(models.Model):
    """datos extra de cada cuenta: rol, universidad y codigo de verificacion"""

    class Rol(models.TextChoices):
        ESTUDIANTE = "estudiante", "Estudiante"
        ENCARGADO = "encargado", "Encargado"
        ADMIN = "admin", "Administrador"

    MINUTOS_CODIGO = 15
    MAX_INTENTOS = 5
    SEGUNDOS_REENVIO = 60

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil"
    )
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.ESTUDIANTE)
    universidad = models.ForeignKey(
        Universidad, on_delete=models.SET_NULL, null=True, blank=True
    )
    codigo = models.CharField(max_length=6, blank=True)
    codigo_creado = models.DateTimeField(null=True, blank=True)
    intentos = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name_plural = "perfiles"

    def __str__(self):
        return f"{self.usuario.username} ({self.get_rol_display()})"

    def nuevo_codigo(self):
        """crea un codigo de 6 digitos y lo guarda"""
        self.codigo = f"{secrets.randbelow(1_000_000):06d}"
        self.codigo_creado = timezone.now()
        self.intentos = 0
        self.save(update_fields=["codigo", "codigo_creado", "intentos"])
        return self.codigo

    def codigo_vencido(self):
        if not self.codigo or not self.codigo_creado:
            return True
        return timezone.now() > self.codigo_creado + timedelta(minutes=self.MINUTOS_CODIGO)

    def puede_reenviar(self):
        if not self.codigo_creado:
            return True
        return timezone.now() > self.codigo_creado + timedelta(seconds=self.SEGUNDOS_REENVIO)


def iniciales(usuario):
    """'vicente.arredondo@usm.cl' -> 'VA', 'admin' -> 'AD'"""
    base = (usuario.email or usuario.username or "?").split("@")[0]
    partes = [p for p in re.split(r"[._\-\s]+", base) if p]
    if len(partes) >= 2:
        return (partes[0][0] + partes[1][0]).upper()
    return (partes[0][:2] if partes else "?").upper()


def rol_de(usuario):
    if not usuario.is_authenticated:
        return None
    if usuario.is_superuser:
        return Perfil.Rol.ADMIN
    perfil = getattr(usuario, "perfil", None)
    return perfil.rol if perfil else Perfil.Rol.ESTUDIANTE
