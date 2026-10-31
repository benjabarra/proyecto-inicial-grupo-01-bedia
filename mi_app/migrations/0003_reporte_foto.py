from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mi_app", "0002_categorias_iniciales"),
    ]

    operations = [
        migrations.AddField(
            model_name="reporte",
            name="foto",
            field=models.ImageField(blank=True, upload_to="reportes/%Y/%m/"),
        ),
    ]
