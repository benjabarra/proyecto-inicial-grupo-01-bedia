# u-pin

reportes de infraestructura del campus san joaquin (usm). equipo 01 bedia.

## correr en local

    python -m venv venv
    venv\Scripts\activate         (windows)
    source venv/bin/activate      (linux/mac)
    pip install -r requirements.txt
    python manage.py migrate
    python manage.py createsuperuser
    python manage.py runserver

abrir http://127.0.0.1:8000/ — tests con `python manage.py test`

## para publicar

variables: DJANGO_SECRET_KEY, DJANGO_DEBUG (0 en produccion), DJANGO_ALLOWED_HOSTS
