# agrega la categoria "Infraestructura" (con su propio icono y color en el mapa).
# si alguien ya la habia creado desde el admin, se deja la misma
from django.db import migrations


def agregar(apps, schema_editor):
    apps.get_model("mi_app", "Categoria").objects.get_or_create(nombre="Infraestructura")


class Migration(migrations.Migration):
    dependencies = [("mi_app", "0010_seguimiento")]

    operations = [migrations.RunPython(agregar, migrations.RunPython.noop)]
