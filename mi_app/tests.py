import shutil
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Categoria, Reporte

MEDIA_TMP = tempfile.mkdtemp()


def foto_de_prueba(nombre="foto.png", tamano=(3000, 2000)):
    buffer = BytesIO()
    Image.new("RGB", tamano, "red").save(buffer, "PNG")
    return SimpleUploadedFile(nombre, buffer.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class CrearReporteTests(TestCase):
    """casos del entregable 3 + foto de evidencia"""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TMP, ignore_errors=True)

    def setUp(self):
        self.usuario = get_user_model().objects.create_user("ana", password="clave-segura-123")
        self.categoria = Categoria.objects.get(nombre="Baño")
        self.client.login(username="ana", password="clave-segura-123")
        self.datos = {
            "titulo": "Baño sin agua",
            "categoria": self.categoria.pk,
            "ubicacion": "Edificio A",
            "descripcion": "El baño de hombres no tiene agua desde la mañana",
        }

    def test_caso_1_reporte_valido_con_foto(self):
        resp = self.client.post(reverse("reportes:crear"), {**self.datos, "foto": foto_de_prueba()})
        reporte = Reporte.objects.get()
        self.assertRedirects(resp, reverse("reportes:detalle", kwargs={"pk": reporte.pk}))
        self.assertEqual(reporte.estado, Reporte.Estado.PENDIENTE)
        self.assertEqual(reporte.autor, self.usuario)
        self.assertTrue(reporte.foto.name.endswith(".jpg"))

    def test_foto_se_achica(self):
        self.client.post(reverse("reportes:crear"), {**self.datos, "foto": foto_de_prueba()})
        with Image.open(Reporte.objects.get().foto.path) as img:
            self.assertLessEqual(max(img.size), 1280)

    def test_caso_2_sin_categoria(self):
        datos = {**self.datos, "categoria": "", "foto": foto_de_prueba()}
        resp = self.client.post(reverse("reportes:crear"), datos)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Reporte.objects.count(), 0)
        self.assertIn("categoria", resp.context["form"].errors)

    def test_sin_foto_no_se_guarda(self):
        resp = self.client.post(reverse("reportes:crear"), self.datos)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Reporte.objects.count(), 0)
        self.assertIn("foto", resp.context["form"].errors)

    def test_archivo_que_no_es_imagen(self):
        falso = SimpleUploadedFile("nota.txt", b"hola", content_type="text/plain")
        resp = self.client.post(reverse("reportes:crear"), {**self.datos, "foto": falso})
        self.assertEqual(Reporte.objects.count(), 0)
        self.assertIn("foto", resp.context["form"].errors)

    def test_requiere_sesion(self):
        self.client.logout()
        resp = self.client.get(reverse("reportes:crear"))
        self.assertEqual(resp.status_code, 302)
