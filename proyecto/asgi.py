# archivo de arranque para servidores (asgi). django lo crea solo; no hace falta tocarlo.

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proyecto.settings')

application = get_asgi_application()
