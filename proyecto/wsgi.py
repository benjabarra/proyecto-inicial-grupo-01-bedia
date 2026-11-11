# archivo de arranque para servidores (wsgi). django lo crea solo; no hace falta tocarlo.

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proyecto.settings')

application = get_wsgi_application()
