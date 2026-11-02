import shutil
import tempfile
from io import BytesIO

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .models import Categoria, Perfil, Reporte, iniciales

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


class CuentasTests(TestCase):
    """registro con correo institucional, codigo de verificacion y tema"""

    datos = {
        "nombre": "Ana Pérez",
        "correo": "ana.perez@usm.cl",
        "password1": "Clave-segura-9271",
        "password2": "Clave-segura-9271",
    }

    def registrar(self, **cambios):
        return self.client.post(reverse("registro"), {**self.datos, **cambios})

    def codigo_enviado(self):
        return Perfil.objects.get(usuario__username="ana.perez@usm.cl").codigo

    # --- bienvenida ---
    def test_bienvenida_muestra_la_universidad(self):
        resp = self.client.get(reverse("bienvenida"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Santa María")

    def test_elegir_universidad_lleva_al_login_con_su_tema(self):
        from .models import Universidad
        usm = Universidad.objects.get(dominio="usm.cl")
        resp = self.client.post(reverse("bienvenida"), {"universidad": usm.pk})
        self.assertRedirects(resp, reverse("login"))
        resp = self.client.get(reverse("login"))
        self.assertContains(resp, "#004B85")
        self.assertContains(resp, "San Joaquín")

    def test_tema_upin_sin_elegir_universidad(self):
        resp = self.client.get(reverse("login"))
        self.assertContains(resp, "#1D1D1F")
        self.assertNotContains(resp, "#004B85")

    # --- registro ---
    def test_registro_crea_cuenta_inactiva_y_manda_codigo(self):
        resp = self.registrar()
        self.assertRedirects(resp, reverse("verificar"))
        usuario = get_user_model().objects.get(username="ana.perez@usm.cl")
        self.assertFalse(usuario.is_active)
        self.assertEqual(usuario.perfil.rol, Perfil.Rol.ESTUDIANTE)
        self.assertEqual(usuario.perfil.universidad.dominio, "usm.cl")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(usuario.perfil.codigo, mail.outbox[0].body)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_acepta_subdominio_de_la_universidad(self):
        resp = self.registrar(correo="ana@sansano.usm.cl")
        self.assertRedirects(resp, reverse("verificar"))

    def test_rechaza_otro_dominio(self):
        resp = self.registrar(correo="ana@gmail.com")
        self.assertIn("correo", resp.context["form"].errors)
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_rechaza_dominio_parecido(self):
        resp = self.registrar(correo="ana@fakeusm.cl")
        self.assertIn("correo", resp.context["form"].errors)

    def test_rechaza_correo_repetido(self):
        get_user_model().objects.create_user("ana.perez@usm.cl", "ana.perez@usm.cl", "x")
        resp = self.registrar()
        self.assertIn("correo", resp.context["form"].errors)

    def test_rechaza_contrasenas_distintas(self):
        resp = self.registrar(password2="otra-cosa-1234")
        self.assertIn("password2", resp.context["form"].errors)
        self.assertEqual(get_user_model().objects.count(), 0)

    # --- codigo ---
    def test_codigo_correcto_activa_y_entra(self):
        self.registrar()
        resp = self.client.post(reverse("verificar"), {"codigo": self.codigo_enviado()})
        self.assertRedirects(resp, reverse("reportes:lista"))
        usuario = get_user_model().objects.get(username="ana.perez@usm.cl")
        self.assertTrue(usuario.is_active)
        self.assertEqual(int(self.client.session["_auth_user_id"]), usuario.pk)

    def test_codigo_incorrecto(self):
        self.registrar()
        malo = "000000" if self.codigo_enviado() != "000000" else "111111"
        resp = self.client.post(reverse("verificar"), {"codigo": malo})
        self.assertIn("codigo", resp.context["form"].errors)
        self.assertFalse(get_user_model().objects.get().is_active)

    def test_codigo_vencido(self):
        self.registrar()
        perfil = Perfil.objects.get()
        perfil.codigo_creado = timezone.now() - timedelta(minutes=16)
        perfil.save()
        resp = self.client.post(reverse("verificar"), {"codigo": perfil.codigo})
        self.assertIn("venció", str(resp.context["form"].errors))

    def test_demasiados_intentos(self):
        self.registrar()
        perfil = Perfil.objects.get()
        perfil.intentos = Perfil.MAX_INTENTOS
        perfil.save()
        resp = self.client.post(reverse("verificar"), {"codigo": perfil.codigo})
        self.assertFalse(get_user_model().objects.get().is_active)
        self.assertIn("intentos", str(resp.context["form"].errors))

    def test_reenviar_espera_un_minuto(self):
        self.registrar()
        self.client.post(reverse("reenviar_codigo"))
        self.assertEqual(len(mail.outbox), 1)  # muy pronto: no manda otro
        perfil = Perfil.objects.get()
        perfil.codigo_creado = timezone.now() - timedelta(seconds=61)
        perfil.save()
        self.client.post(reverse("reenviar_codigo"))
        self.assertEqual(len(mail.outbox), 2)

    # --- iniciar sesion ---
    def test_login_sin_verificar_pide_codigo(self):
        self.registrar()
        self.client.session.flush()
        resp = self.client.post(reverse("login"), {"correo": "ana.perez@usm.cl", "password": "Clave-segura-9271"})
        self.assertRedirects(resp, reverse("verificar"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_verificado(self):
        get_user_model().objects.create_user("ana.perez@usm.cl", "ana.perez@usm.cl", "Clave-segura-9271")
        resp = self.client.post(reverse("login"), {"correo": "ANA.PEREZ@usm.cl", "password": "Clave-segura-9271"})
        self.assertRedirects(resp, reverse("reportes:lista"))

    def test_login_contrasena_mala(self):
        get_user_model().objects.create_user("ana.perez@usm.cl", "ana.perez@usm.cl", "Clave-segura-9271")
        resp = self.client.post(reverse("login"), {"correo": "ana.perez@usm.cl", "password": "otra"})
        self.assertContains(resp, "incorrectos")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_admin_entra_con_usuario_sin_correo_usm(self):
        get_user_model().objects.create_superuser("admin", "", "Clave-admin-5531")
        resp = self.client.post(reverse("login"), {"correo": "admin", "password": "Clave-admin-5531"})
        self.assertRedirects(resp, reverse("reportes:lista"))
        resp = self.client.get(reverse("reportes:lista"))
        self.assertContains(resp, "Administrar")

    def test_next_externo_no_se_sigue(self):
        get_user_model().objects.create_user("ana.perez@usm.cl", "ana.perez@usm.cl", "Clave-segura-9271")
        resp = self.client.post(
            reverse("login") + "?next=https://malo.com/",
            {"correo": "ana.perez@usm.cl", "password": "Clave-segura-9271"},
        )
        self.assertRedirects(resp, reverse("reportes:lista"))

    # --- perfil y tema ---
    def test_iniciales(self):
        User = get_user_model()
        self.assertEqual(iniciales(User(username="vicente.arredondo@usm.cl", email="vicente.arredondo@usm.cl")), "VA")
        self.assertEqual(iniciales(User(username="ana@usm.cl", email="ana@usm.cl")), "AN")
        self.assertEqual(iniciales(User(username="admin")), "AD")

    def test_tema_usm_y_avatar_despues_de_entrar(self):
        self.registrar()
        self.client.post(reverse("verificar"), {"codigo": self.codigo_enviado()})
        resp = self.client.get(reverse("reportes:lista"))
        self.assertContains(resp, "#004B85")
        self.assertContains(resp, "usm-san-joaquin.jpg")
        self.assertContains(resp, ">AP</span>")


class EstadosTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user("ana", password="clave-segura-123")
        self.client.login(username="ana", password="clave-segura-123")
        cat = Categoria.objects.first()
        for estado in ["pendiente", "en_proceso", "resuelto"]:
            Reporte.objects.create(titulo=estado, descripcion="x", categoria=cat, ubicacion="A", estado=estado, autor=self.usuario)

    def test_solo_tres_estados(self):
        self.assertEqual([v for v, _ in Reporte.Estado.choices], ["pendiente", "en_proceso", "resuelto"])

    def test_filtro_activos_oculta_resueltos(self):
        resp = self.client.get(reverse("reportes:lista") + "?ver=activos")
        self.assertEqual({r.titulo for r in resp.context["reportes"]}, {"pendiente", "en_proceso"})
