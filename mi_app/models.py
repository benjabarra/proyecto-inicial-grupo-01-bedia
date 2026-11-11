# modelos de u-pin: las tablas de la base de datos.
# categorias, edificios, salas, reportes, apoyos, universidades, campus y perfiles.

# librerias que usan los modelos
import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


# tipo de problema (baños, iluminación, etc.). cada reporte tiene una
class Categoria(models.Model):
    nombre = models.CharField(max_length=60, unique=True)

    class Meta:
        verbose_name_plural = "categorías"

    def __str__(self):
        return self.nombre


# edificio del campus (a, b, c, e, f, k, l) con la lista de pisos que tiene
class Edificio(models.Model):
    letra = models.CharField(max_length=5, unique=True)
    nombre = models.CharField(max_length=80)
    pisos = models.JSONField(default=list, help_text="pisos que tiene, ej: [-2, -1, 1, 2, 3]")

    class Meta:
        ordering = ["letra"]

    def __str__(self):
        return self.nombre


# sala o espacio de un edificio. se carga desde datos/salas_san_joaquin.json
class Sala(models.Model):
    """una sala o espacio del campus. 'forma' son sus esquinas en el plano del mapa"""

    # tipos de sala que se pueden elegir
    class Tipo(models.TextChoices):
        SALA = "sala", "Sala de clases"
        OFICINA = "oficina", "Oficina o departamento"
        AUDITORIO = "auditorio", "Auditorio"
        SERVICIO = "servicio", "Baño o servicio"
        COMIDA = "comida", "Casino o cafetería"
        DEPORTE = "deporte", "Deportes"
        ESPACIO = "espacio", "Patio o espacio común"
        ACCESO = "acceso", "Acceso"

    edificio = models.ForeignKey(Edificio, on_delete=models.CASCADE, related_name="salas")  # edificio al que pertenece
    piso = models.SmallIntegerField()  # piso: -2, -1, 1, 2 ...
    nombre = models.CharField(max_length=80)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.SALA)
    forma = models.JSONField(default=list, blank=True)  # esquinas de la sala en el plano del mapa
    extra = models.JSONField(
        default=dict, blank=True, help_text="datos de dibujo del mapa (tipo de bloque, etiqueta, etc.)"
    )

    class Meta:
        ordering = ["edificio__letra", "piso", "nombre"]
        verbose_name_plural = "salas"

    def __str__(self):
        return f"{self.nombre} · {self.edificio} · Piso {self.piso}"

    # centro de la sala: ahi se dibuja el pin de sus reportes
    def centro(self):
        """punto medio de la forma, para poner el pin del reporte"""
        if not self.forma:
            return None
        xs = [p[0] for p in self.forma]
        ys = [p[1] for p in self.forma]
        return (sum(xs) / len(xs), sum(ys) / len(ys))


# un problema reportado por una persona: que pasa, donde y en que estado esta
class Reporte(models.Model):
    # los tres estados posibles de un reporte
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        EN_PROCESO = "en_proceso", "En proceso"
        RESUELTO = "resuelto", "Resuelto"

    titulo = models.CharField(max_length=120)  # resumen corto del problema
    descripcion = models.TextField()  # detalle del problema
    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name="reportes"
    )
    sala = models.ForeignKey(
        Sala, on_delete=models.SET_NULL, null=True, blank=True, related_name="reportes"
    )
    ubicacion = models.CharField(
        max_length=150, help_text="Edificio, sala o zona del campus"
    )
    foto = models.ImageField(upload_to="reportes/%Y/%m/", blank=True)  # foto opcional (se achica al guardar)
    latitud = models.FloatField(null=True, blank=True)
    longitud = models.FloatField(null=True, blank=True)
    # punto exacto en el mapa (coordenadas del plano) y piso: "ext", "-1", "1", ...
    piso = models.CharField(max_length=4, blank=True)  # piso del punto en el mapa
    mapa_x = models.FloatField(null=True, blank=True)  # posicion x del pin en el plano
    mapa_y = models.FloatField(null=True, blank=True)  # posicion y del pin en el plano
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.PENDIENTE
    )
    autor = models.ForeignKey(  # quien hizo el reporte
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reportes"
    )
    creado = models.DateTimeField(auto_now_add=True)  # fecha de creacion
    actualizado = models.DateTimeField(auto_now=True)  # ultima modificacion

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return f"{self.titulo} ({self.get_estado_display()})"

    # lugar del pin en el mapa: el punto que marco la persona o el centro de la sala
    def punto_mapa(self):
        """(piso, x, y) donde va el pin, o None si no se sabe"""
        if self.mapa_x is not None and self.mapa_y is not None:
            piso = self.piso or (str(self.sala.piso) if self.sala else "ext")
            return piso, self.mapa_x, self.mapa_y
        if self.sala and self.sala.centro():
            x, y = self.sala.centro()
            return str(self.sala.piso), x, y
        return None


# cada "a mi tambien me pasa". una persona puede apoyar un reporte una sola vez
class Apoyo(models.Model):
    """'a mi tambien me pasa': una persona apoya un reporte una sola vez"""

    reporte = models.ForeignKey(Reporte, on_delete=models.CASCADE, related_name="apoyos")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="apoyos"
    )
    creado = models.DateTimeField(auto_now_add=True)  # fecha de creacion

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["reporte", "usuario"], name="un_apoyo_por_persona")
        ]

    def __str__(self):
        return f"{self.usuario} apoya «{self.reporte.titulo}»"


# clave corta de cada categoria para el mapa (icono y color del pin)
CLAVE_CATEGORIA = {
    "Baños": "bano",
    "Agua y goteras": "agua",
    "Climatización": "clima",
    "Iluminación": "luz",
    "Electricidad y enchufes": "elec",
    "Internet y WiFi": "wifi",
    "Proyector y equipos": "equipo",
    "Mobiliario": "mueble",
    "Puertas, ventanas y cerraduras": "puerta",
    "Daños en muro, techo o piso": "danos",
    "Aseo y basura": "aseo",
    "Áreas verdes y exteriores": "verde",
    "Ascensor, escaleras y rampas": "ascensor",
    "Otro": "otro",
}


# universidad (usm, uch, puc, usach). da los colores y el dominio de correo aceptado
class Universidad(models.Model):
    """datos de cada universidad: el tema de la pagina sale de aqui"""

    nombre = models.CharField(max_length=120)
    sigla = models.CharField(max_length=20)
    campus = models.CharField(max_length=80)
    dominio = models.CharField(max_length=100, unique=True)  # final del correo aceptado, ej: usm.cl
    color_primario = models.CharField(max_length=7)
    color_acento = models.CharField(max_length=7)
    imagen = models.CharField(max_length=200, blank=True)
    activa = models.BooleanField(default=True, help_text="si no, sale gris y dice Próximamente")

    class Meta:
        verbose_name_plural = "universidades"

    def __str__(self):
        return f"{self.sigla} {self.campus}"


# sede de una universidad. por ahora solo san joaquin esta activo
class Campus(models.Model):
    """cada sede de una universidad. solo los activos se pueden elegir"""

    universidad = models.ForeignKey(Universidad, on_delete=models.CASCADE, related_name="campus_set")
    nombre = models.CharField(max_length=80)
    ciudad = models.CharField(max_length=80, blank=True)
    activo = models.BooleanField(default=False, help_text="si no, sale gris y dice Próximamente")
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["universidad", "orden", "nombre"]
        verbose_name_plural = "campus"

    def __str__(self):
        return f"{self.universidad.sigla} · {self.nombre}"


# busca la universidad segun el final del correo (ej: @usm.cl)
def universidad_para_correo(correo):
    """devuelve la universidad que corresponde al dominio del correo, o None"""
    if not correo or "@" not in correo:
        return None
    dominio = correo.rsplit("@", 1)[-1].strip().lower()
    for uni in Universidad.objects.filter(activa=True):
        if dominio == uni.dominio or dominio.endswith("." + uni.dominio):
            return uni
    return None


# datos extra de cada usuario: rol, universidad, campus y codigo de verificacion
class Perfil(models.Model):
    """datos extra de cada cuenta: rol, universidad y codigo de verificacion"""

    # roles: estudiante reporta, encargado cambia estados, admin administra todo
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
    campus = models.ForeignKey(Campus, on_delete=models.SET_NULL, null=True, blank=True)
    codigo = models.CharField(max_length=6, blank=True)
    codigo_creado = models.DateTimeField(null=True, blank=True)
    intentos = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name_plural = "perfiles"

    def __str__(self):
        return f"{self.usuario.username} ({self.get_rol_display()})"

    # crea un codigo de 6 numeros para confirmar el correo
    def nuevo_codigo(self):
        """crea un codigo de 6 digitos y lo guarda"""
        self.codigo = f"{secrets.randbelow(1_000_000):06d}"
        self.codigo_creado = timezone.now()
        self.intentos = 0
        self.save(update_fields=["codigo", "codigo_creado", "intentos"])
        return self.codigo

    # true si el codigo ya paso los 15 minutos
    def codigo_vencido(self):
        if not self.codigo or not self.codigo_creado:
            return True
        return timezone.now() > self.codigo_creado + timedelta(minutes=self.MINUTOS_CODIGO)

    # evita pedir codigos seguidos: hay que esperar un minuto
    def puede_reenviar(self):
        if not self.codigo_creado:
            return True
        return timezone.now() > self.codigo_creado + timedelta(seconds=self.SEGUNDOS_REENVIO)


# letras del avatar (ej: vicente.arredondo -> va)
def iniciales(usuario):
    """nombre 'ana' y apellido 'perez' -> 'AP'; sin nombre: 'vicente.arredondo@usm.cl' -> 'VA', 'admin' -> 'AD'"""
    nombre = f"{usuario.first_name or ''} {usuario.last_name or ''}".split()
    if len(nombre) >= 2:
        return (nombre[0][0] + nombre[-1][0]).upper()
    base = (usuario.email or usuario.username or "?").split("@")[0]
    partes = [p for p in re.split(r"[._\-\s]+", base) if p]
    if len(partes) >= 2:
        return (partes[0][0] + partes[1][0]).upper()
    return (partes[0][:2] if partes else "?").upper()


# devuelve el rol del usuario; el superusuario siempre es admin
def rol_de(usuario):
    if not usuario.is_authenticated:
        return None
    if usuario.is_superuser:
        return Perfil.Rol.ADMIN
    perfil = getattr(usuario, "perfil", None)
    return perfil.rol if perfil else Perfil.Rol.ESTUDIANTE
