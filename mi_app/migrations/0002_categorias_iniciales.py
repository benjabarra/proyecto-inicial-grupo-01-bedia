from django.db import migrations

CATEGORIAS = [
    "Baño",
    "Iluminación",
    "Filtración o gotera",
    "Mobiliario",
    "Aseo",
    "Ascensor o escalera",
    "Climatización",
    "Electricidad o internet",
    "Otro",
]


def crear_categorias(apps, schema_editor):
    Categoria = apps.get_model("mi_app", "Categoria")
    for nombre in CATEGORIAS:
        Categoria.objects.get_or_create(nombre=nombre)


class Migration(migrations.Migration):

    dependencies = [
        ("mi_app", "0001_initial"),
    ]

    operations = [
        # No se borran las categorías al revertir: podrían tener reportes asociados.
        migrations.RunPython(crear_categorias, migrations.RunPython.noop),
    ]
