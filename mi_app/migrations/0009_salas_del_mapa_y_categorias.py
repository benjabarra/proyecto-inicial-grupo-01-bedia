"""paso 5: carga todas las salas del mapa oficial y deja las 14 categorias del mapa"""

import json
from pathlib import Path

from django.db import migrations

DATOS = Path(__file__).resolve().parent.parent / "datos" / "salas_san_joaquin.json"

# nombres antiguos -> nombres del mapa (asi los reportes viejos no pierden su categoria)
RENOMBRAR = {
    "Baño": "Baños",
    "Filtración o gotera": "Agua y goteras",
    "Electricidad o internet": "Electricidad y enchufes",
    "Aseo": "Aseo y basura",
    "Ascensor o escalera": "Ascensor, escaleras y rampas",
}
CATEGORIAS = [
    "Baños",
    "Agua y goteras",
    "Climatización",
    "Iluminación",
    "Electricidad y enchufes",
    "Internet y WiFi",
    "Proyector y equipos",
    "Mobiliario",
    "Puertas, ventanas y cerraduras",
    "Daños en muro, techo o piso",
    "Aseo y basura",
    "Áreas verdes y exteriores",
    "Ascensor, escaleras y rampas",
    "Otro",
]


def categorias(apps, schema_editor):
    Categoria = apps.get_model("mi_app", "Categoria")
    for viejo, nuevo in RENOMBRAR.items():
        Categoria.objects.filter(nombre=viejo).exclude(
            nombre__in=Categoria.objects.filter(nombre=nuevo).values("nombre")
        ).update(nombre=nuevo)
    for nombre in CATEGORIAS:
        Categoria.objects.get_or_create(nombre=nombre)


def salas(apps, schema_editor):
    """reemplaza las salas por las del mapa oficial. los reportes guardan su texto de ubicacion"""
    Edificio = apps.get_model("mi_app", "Edificio")
    Sala = apps.get_model("mi_app", "Sala")
    Reporte = apps.get_model("mi_app", "Reporte")
    datos = json.loads(DATOS.read_text(encoding="utf-8"))
    edificios = {}
    for e in datos["edificios"]:
        ed, _ = Edificio.objects.update_or_create(
            letra=e["letra"], defaults={"nombre": e["nombre"], "pisos": e["pisos"]}
        )
        edificios[e["letra"]] = ed
    # los reportes que tenian sala la recuperan por nombre, edificio y piso
    antes = {
        r.pk: (r.sala.edificio.letra, r.sala.piso, r.sala.nombre)
        for r in Reporte.objects.filter(sala__isnull=False).select_related("sala__edificio")
    }
    Sala.objects.all().delete()
    Sala.objects.bulk_create(
        Sala(
            edificio=edificios[s["edificio"]],
            piso=s["piso"],
            nombre=s["nombre"],
            tipo=s["tipo"],
            forma=s["forma"],
            extra=s.get("extra", {}),
        )
        for s in datos["salas"]
    )
    for pk, (letra, piso, nombre) in antes.items():
        sala = Sala.objects.filter(edificio__letra=letra, piso=piso, nombre=nombre).first()
        if sala:
            Reporte.objects.filter(pk=pk).update(sala=sala)


class Migration(migrations.Migration):

    dependencies = [
        ("mi_app", "0008_mapa_y_apoyos"),
    ]

    operations = [
        migrations.RunPython(categorias, migrations.RunPython.noop),
        migrations.RunPython(salas, migrations.RunPython.noop),
    ]
