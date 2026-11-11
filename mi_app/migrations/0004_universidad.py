# migracion 0004: agrega las universidades y sus colores
from django.db import migrations, models


def crear_usm(apps, schema_editor):
    Universidad = apps.get_model("mi_app", "Universidad")
    Universidad.objects.get_or_create(
        dominio="usm.cl",
        defaults={
            "nombre": "Universidad Técnica Federico Santa María",
            "sigla": "USM",
            "campus": "San Joaquín",
            "color_primario": "#004B85",
            "color_acento": "#F7AE00",
            "imagen": "mi_app/img/usm-san-joaquin.jpg",
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("mi_app", "0003_reporte_foto"),
    ]

    operations = [
        migrations.CreateModel(
            name="Universidad",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=120)),
                ("sigla", models.CharField(max_length=20)),
                ("campus", models.CharField(max_length=80)),
                ("dominio", models.CharField(max_length=100, unique=True)),
                ("color_primario", models.CharField(max_length=7)),
                ("color_acento", models.CharField(max_length=7)),
                ("imagen", models.CharField(blank=True, max_length=200)),
            ],
            options={
                "verbose_name_plural": "universidades",
            },
        ),
        migrations.RunPython(crear_usm, migrations.RunPython.noop),
    ]
