# configuracion del proyecto django de u-pin.
# los datos secretos (clave, correo) se leen de variables de entorno, nunca se escriben aqui.

import os
from pathlib import Path

# carpeta principal del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent


# ajustes de desarrollo (no usar asi en produccion)

# clave secreta de django: en produccion va en DJANGO_SECRET_KEY
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'clave-solo-para-desarrollo-no-usar-en-produccion',
)

# modo depuracion: muestra errores detallados (apagar en produccion)
DEBUG = os.environ.get('DJANGO_DEBUG', '1') == '1'

# direcciones desde donde se puede abrir la pagina
ALLOWED_HOSTS = [
    h for h in os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',') if h
]

# para probar en codespaces: DJANGO_CSRF_TRUSTED_ORIGINS=https://*.app.github.dev
CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if o
]


# dentro de github codespaces la pagina se abre por una direccion *.app.github.dev:
# en modo desarrollo se aceptan solas, sin tener que escribir los export cada vez
if DEBUG and os.environ.get("CODESPACES") == "true":
    ALLOWED_HOSTS += ["*"]
    CSRF_TRUSTED_ORIGINS += ["https://*.app.github.dev", "https://localhost:8000", "http://localhost:8000"]


# apps instaladas: las de django y la nuestra (mi_app)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'mi_app',
]

# capas que procesan cada visita (sesion, seguridad, mensajes)
MIDDLEWARE = [
    'django.middleware.gzip.GZipMiddleware',  # comprime las paginas (el mapa pesa ~5 veces menos al viajar)
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# archivo con las direcciones principales
ROOT_URLCONF = 'proyecto.urls'

# plantillas html; 'tema' agrega colores e iniciales a todas las paginas
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'mi_app.context_processors.tema',
            ],
        },
    },
]

# punto de entrada para servidores
WSGI_APPLICATION = 'proyecto.wsgi.application'


# base de datos: un archivo sqlite (db.sqlite3) que no se sube a github

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# reglas para contraseñas seguras

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# idioma y hora



USE_I18N = True

USE_TZ = True


# archivos fijos: css, javascript, imagenes y el mapa

STATIC_URL = 'static/'


# correo para los codigos de verificacion

# sin configurar, los correos (codigo de verificacion) salen en la terminal.
# para mandarlos de verdad: DJANGO_EMAIL_HOST, DJANGO_EMAIL_USER y DJANGO_EMAIL_PASSWORD
EMAIL_HOST = os.environ.get("DJANGO_EMAIL_HOST", "")
if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_PORT = int(os.environ.get("DJANGO_EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.environ.get("DJANGO_EMAIL_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("DJANGO_EMAIL_PASSWORD", "")
    EMAIL_USE_TLS = True
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = os.environ.get("DJANGO_EMAIL_FROM", "U-Pin <no-responder@upin.cl>")


# a donde ir para entrar, despues de entrar y despues de salir
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "reportes:mapa"

# si un formulario llega con el token de seguridad vencido se muestra una pagina en español para reintentar
CSRF_FAILURE_VIEW = "mi_app.views.csrf_fallo"
LOGOUT_REDIRECT_URL = "login"

# español y hora de chile
LANGUAGE_CODE = "es"
TIME_ZONE = "America/Santiago"

# fotos subidas por usuarios
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
