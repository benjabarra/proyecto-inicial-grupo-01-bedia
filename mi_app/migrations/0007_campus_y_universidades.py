# migracion 0007: agrega los campus de cada universidad
from django.db import migrations, models
import django.db.models.deletion


# (sigla, nombre, dominio, color, acento)
OTRAS = [
    ("UCH", "Universidad de Chile", "uchile.cl", "#1F5592", "#E30613"),
    ("PUC", "Pontificia Universidad Católica", "uc.cl", "#173F8A", "#0176DE"),
    ("USACH", "Universidad de Santiago", "usach.cl", "#EA7600", "#1D1D1F"),
]

# (nombre, ciudad, activo)
CAMPUS_USM = [
    ("Campus San Joaquín", "Santiago", True),
    ("Casa Central", "Valparaíso", False),
    ("Campus Vitacura", "Santiago", False),
    ("Sede Viña del Mar", "José Miguel Carrera", False),
    ("Sede Concepción", "Rey Balduino de Bélgica", False),
]


def cargar(apps, schema_editor):
    Universidad = apps.get_model("mi_app", "Universidad")
    Campus = apps.get_model("mi_app", "Campus")
    Perfil = apps.get_model("mi_app", "Perfil")
    usm = Universidad.objects.filter(dominio="usm.cl").first()
    if usm:
        for orden, (nombre, ciudad, activo) in enumerate(CAMPUS_USM):
            Campus.objects.get_or_create(
                universidad=usm, nombre=nombre,
                defaults={"ciudad": ciudad, "activo": activo, "orden": orden},
            )
        sj = Campus.objects.get(universidad=usm, nombre="Campus San Joaquín")
        Perfil.objects.filter(universidad=usm, campus__isnull=True).update(campus=sj)
    for sigla, nombre, dominio, color, acento in OTRAS:
        Universidad.objects.get_or_create(
            dominio=dominio,
            defaults={
                "sigla": sigla, "nombre": nombre, "campus": "",
                "color_primario": color, "color_acento": acento, "activa": False,
            },
        )


def descargar(apps, schema_editor):
    Universidad = apps.get_model("mi_app", "Universidad")
    Universidad.objects.filter(activa=False).delete()


class Migration(migrations.Migration):

    dependencies = [("mi_app", "0006_edificios_y_salas")]

    operations = [
        migrations.AddField(
            model_name="universidad",
            name="activa",
            field=models.BooleanField(default=True, help_text="si no, sale gris y dice Próximamente"),
        ),
        migrations.CreateModel(
            name="Campus",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=80)),
                ("ciudad", models.CharField(blank=True, max_length=80)),
                ("activo", models.BooleanField(default=False, help_text="si no, sale gris y dice Próximamente")),
                ("orden", models.PositiveSmallIntegerField(default=0)),
                ("universidad", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="campus_set", to="mi_app.universidad")),
            ],
            options={"verbose_name_plural": "campus", "ordering": ["universidad", "orden", "nombre"]},
        ),
        migrations.AddField(
            model_name="perfil",
            name="campus",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="mi_app.campus"),
        ),
        migrations.RunPython(cargar, descargar),
    ]
