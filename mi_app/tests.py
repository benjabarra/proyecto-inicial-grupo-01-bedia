# pruebas automaticas: se corren con python manage.py test.
# cada clase prueba una parte de la app
import shutil
import tempfile
from pathlib import Path
from io import BytesIO, StringIO

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .models import Categoria, Edificio, Perfil, Reporte, Sala, Seguimiento, iniciales

# carpeta temporal para las fotos de prueba (se borra al terminar)
MEDIA_TMP = tempfile.mkdtemp()


# crea una imagen falsa para probar la subida de fotos
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
        self.categoria = Categoria.objects.get(nombre="Baños")
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

    def test_sin_foto_tambien_se_guarda(self):
        resp = self.client.post(reverse("reportes:crear"), self.datos)
        reporte = Reporte.objects.get()
        self.assertRedirects(resp, reverse("reportes:detalle", kwargs={"pk": reporte.pk}))
        self.assertFalse(reporte.foto)

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
        "nombre": "Ana",
        "apellido": "Pérez",
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
        from .models import Campus
        sj = Campus.objects.get(nombre="Campus San Joaquín")
        resp = self.client.post(reverse("bienvenida"), {"campus": sj.pk})
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
        # el nombre y el apellido quedan guardados por separado
        self.assertEqual((usuario.first_name, usuario.last_name), ("Ana", "Pérez"))

    def test_registro_pide_apellido(self):
        resp = self.registrar(apellido="")
        self.assertIn("apellido", resp.context["form"].errors)
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
        self.assertRedirects(resp, reverse("reportes:mapa"))
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
        self.assertRedirects(resp, reverse("reportes:mapa"))

    def test_login_contrasena_mala(self):
        get_user_model().objects.create_user("ana.perez@usm.cl", "ana.perez@usm.cl", "Clave-segura-9271")
        resp = self.client.post(reverse("login"), {"correo": "ana.perez@usm.cl", "password": "otra"})
        self.assertContains(resp, "incorrectos")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_admin_entra_con_usuario_sin_correo_usm(self):
        get_user_model().objects.create_superuser("admin", "", "Clave-admin-5531")
        resp = self.client.post(reverse("login"), {"correo": "admin", "password": "Clave-admin-5531"})
        self.assertRedirects(resp, reverse("reportes:mapa"))
        resp = self.client.get(reverse("reportes:lista"))
        self.assertContains(resp, "Administrar")

    def test_next_externo_no_se_sigue(self):
        get_user_model().objects.create_user("ana.perez@usm.cl", "ana.perez@usm.cl", "Clave-segura-9271")
        resp = self.client.post(
            reverse("login") + "?next=https://malo.com/",
            {"correo": "ana.perez@usm.cl", "password": "Clave-segura-9271"},
        )
        self.assertRedirects(resp, reverse("reportes:mapa"))

    # --- perfil y tema ---
    def test_iniciales(self):
        User = get_user_model()
        self.assertEqual(iniciales(User(username="vicente.arredondo@usm.cl", email="vicente.arredondo@usm.cl")), "VA")
        self.assertEqual(iniciales(User(username="ana@usm.cl", email="ana@usm.cl")), "AN")
        self.assertEqual(iniciales(User(username="admin")), "AD")
        # con nombre y apellido se usan esos
        self.assertEqual(iniciales(User(username="x@usm.cl", email="x@usm.cl", first_name="Daniela", last_name="Bustos")), "DB")

    def test_tema_usm_y_avatar_despues_de_entrar(self):
        self.registrar()
        self.client.post(reverse("verificar"), {"codigo": self.codigo_enviado()})
        resp = self.client.get(reverse("reportes:lista"))
        self.assertContains(resp, "#004B85")
        self.assertContains(resp, "usm-san-joaquin.jpg")
        self.assertContains(resp, ">AP</a>")


# pruebas de los tres estados y el filtro de activos
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


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class SalasTests(TestCase):
    """edificios y salas cargados desde el plano"""

    def setUp(self):
        get_user_model().objects.create_user("ana", password="clave-segura-123")
        self.client.login(username="ana", password="clave-segura-123")
        self.a010 = Sala.objects.get(nombre="A010")
        self.datos = {
            "titulo": "La luz parpadea",
            "categoria": Categoria.objects.get(nombre="Baños").pk,
            "descripcion": "El tubo del fondo parpadea",
        }

    def test_salas_cargadas(self):
        self.assertGreaterEqual(Sala.objects.count(), 100)
        self.assertEqual(self.a010.edificio.letra, "A")
        self.assertEqual(self.a010.piso, 1)
        self.assertTrue(len(self.a010.forma) >= 4)
        self.assertIn(-2, Edificio.objects.get(letra="K").pisos)
        self.assertTrue(Sala.objects.filter(edificio__letra="K", piso=3).exists())

    def test_reporte_con_sala(self):
        resp = self.client.post(reverse("reportes:crear"), {**self.datos, "sala": self.a010.pk, "foto": foto_de_prueba()})
        reporte = Reporte.objects.get()
        self.assertRedirects(resp, reverse("reportes:detalle", kwargs={"pk": reporte.pk}))
        self.assertEqual(reporte.sala, self.a010)
        self.assertEqual(reporte.ubicacion, "A010 · Edificio A · Piso 1")
        resp = self.client.get(reverse("reportes:detalle", kwargs={"pk": reporte.pk}))
        self.assertContains(resp, "<dt>Sala</dt>")

    def test_reporte_con_sala_y_detalle(self):
        self.client.post(reverse("reportes:crear"), {**self.datos, "sala": self.a010.pk, "ubicacion": "al fondo", "foto": foto_de_prueba()})
        self.assertEqual(Reporte.objects.get().ubicacion, "A010 · Edificio A · Piso 1 · al fondo")

    def test_sin_sala_ni_ubicacion(self):
        resp = self.client.post(reverse("reportes:crear"), {**self.datos, "foto": foto_de_prueba()})
        self.assertEqual(Reporte.objects.count(), 0)
        self.assertIn("ubicacion", resp.context["form"].errors)

    def test_reportar_aqui_marca_la_sala(self):
        resp = self.client.get(reverse("reportes:crear") + f"?sala={self.a010.pk}")
        self.assertEqual(str(resp.context["form"]["sala"].value()), str(self.a010.pk))


# pruebas de campus, bienvenida y perfil
class CampusYPerfilTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            "ana@usm.cl", email="ana@usm.cl", password="clave-segura-123", first_name="Ana Pérez"
        )
        from .models import Campus, Universidad
        self.usm = Universidad.objects.get(dominio="usm.cl")
        self.sj = Campus.objects.get(nombre="Campus San Joaquín")
        Perfil.objects.create(usuario=self.usuario, universidad=self.usm, campus=self.sj)

    def test_bienvenida_muestra_otras_universidades_bloqueadas(self):
        resp = self.client.get(reverse("bienvenida"))
        for sigla in ("UCH", "PUC", "USACH"):
            self.assertContains(resp, sigla)
        self.assertContains(resp, "Próximamente")
        self.assertContains(resp, "Casa Central")

    def test_no_se_puede_elegir_campus_bloqueado(self):
        from .models import Campus
        casa = Campus.objects.get(nombre="Casa Central")
        resp = self.client.post(reverse("bienvenida"), {"campus": casa.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("campus_id", self.client.session)

    def test_universidad_bloqueada_no_acepta_correos(self):
        from .models import universidad_para_correo
        self.assertIsNone(universidad_para_correo("x@uc.cl"))
        self.assertEqual(universidad_para_correo("x@usm.cl"), self.usm)

    def test_campus_elegido_se_guarda_al_entrar(self):
        self.usuario.perfil.campus = None
        self.usuario.perfil.save()
        self.client.post(reverse("bienvenida"), {"campus": self.sj.pk})
        self.client.post(reverse("login"), {"correo": "ana@usm.cl", "password": "clave-segura-123"})
        self.usuario.perfil.refresh_from_db()
        self.assertEqual(self.usuario.perfil.campus, self.sj)

    def test_perfil_requiere_sesion(self):
        resp = self.client.get(reverse("reportes:perfil"))
        self.assertEqual(resp.status_code, 302)

    def test_perfil_muestra_datos_y_cifras(self):
        self.client.login(username="ana@usm.cl", password="clave-segura-123")
        cat = Categoria.objects.get(nombre="Baños")
        Reporte.objects.create(titulo="a", descripcion="d", categoria=cat, ubicacion="x", autor=self.usuario)
        Reporte.objects.create(titulo="b", descripcion="d", categoria=cat, ubicacion="x", autor=self.usuario,
                               estado=Reporte.Estado.RESUELTO)
        resp = self.client.get(reverse("reportes:perfil"))
        self.assertContains(resp, "Ana Pérez")
        self.assertContains(resp, "Campus San Joaquín")
        self.assertEqual(resp.context["total"], 2)
        self.assertEqual(resp.context["resueltos"], 1)

    def test_perfil_muestra_nombre_y_apellido(self):
        self.usuario.first_name, self.usuario.last_name = "Ana", "Pérez"
        self.usuario.save()
        self.client.login(username="ana@usm.cl", password="clave-segura-123")
        resp = self.client.get(reverse("reportes:perfil"))
        self.assertContains(resp, "<h1>Ana Pérez</h1>", html=True)
        # el nombre ya no se cambia desde el perfil
        self.assertNotContains(resp, 'name="accion" value="nombre"')

    def test_registro_sin_mencion_a_sansano(self):
        self.assertNotContains(self.client.get(reverse("registro")), "sansano")

    def test_barra_inferior_solo_con_sesion(self):
        self.assertNotContains(self.client.get(reverse("login")), "barra-inferior")
        self.client.login(username="ana@usm.cl", password="clave-segura-123")
        self.assertContains(self.client.get(reverse("reportes:lista")), "barra-inferior")

    def test_perfil_funciona_para_admin_sin_perfil(self):
        admin = get_user_model().objects.create_superuser("jefe", password="clave-segura-123")
        self.client.login(username="jefe", password="clave-segura-123")
        resp = self.client.get(reverse("reportes:perfil"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Administrador")
        self.assertTrue(Perfil.objects.filter(usuario=admin).exists())

    def test_bienvenida_no_trae_campus_preseleccionado(self):
        resp = self.client.get(reverse("bienvenida"))
        self.assertNotContains(resp, "checked")

    def test_continuar_sin_elegir_campus_avisa(self):
        resp = self.client.post(reverse("bienvenida"), {})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Elige tu campus")

    def test_bienvenida_trae_la_foto_dentro_de_la_universidad(self):
        resp = self.client.get(reverse("bienvenida"))
        self.assertContains(resp, 'class="foto-uni"')
        self.assertContains(resp, "data-uni")


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class MapaYApoyosTests(TestCase):
    """paso 5: mapa con datos de la base de datos, reportar en un punto y apoyos"""

    def setUp(self):
        self.ana = get_user_model().objects.create_user("ana", password="clave-segura-123")
        self.beto = get_user_model().objects.create_user("beto", password="clave-segura-123")
        self.client.login(username="ana", password="clave-segura-123")
        self.cat = Categoria.objects.get(nombre="Iluminación")
        self.a010 = Sala.objects.get(nombre="A010")

    def test_catorce_categorias_del_mapa(self):
        from .models import CLAVE_CATEGORIA
        for nombre in CLAVE_CATEGORIA:
            self.assertTrue(Categoria.objects.filter(nombre=nombre).exists(), nombre)

    def test_salas_del_mapa_oficial(self):
        self.assertTrue(Sala.objects.filter(nombre="Sala LDS").exists())
        self.assertFalse(Sala.objects.filter(nombre="Sala LSD").exists())
        self.assertTrue(Sala.objects.filter(edificio__letra="K", piso=6, nombre="DINF").exists())
        self.assertEqual(Edificio.objects.get(letra="B").pisos, [1, 2])
        self.assertEqual(Sala.objects.get(nombre="B038 LPA").extra["full"], "Laboratorio de Programación Avanzada")

    def test_mapa_requiere_sesion(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("reportes:mapa")).status_code, 302)

    def test_mapa_trae_salas_y_reportes(self):
        Reporte.objects.create(titulo="Luz", descripcion="d", categoria=self.cat, sala=self.a010,
                               ubicacion="A010", autor=self.ana)
        resp = self.client.get(reverse("reportes:mapa"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="d-pisos"')
        piso1 = resp.context["pisos"]["1"]
        self.assertTrue(any(s["label"] == "A010" and s["pk"] == self.a010.pk for s in piso1))
        rep = resp.context["reportes"][0]
        self.assertEqual((rep["cat"], rep["f"], rep["salapk"]), ("luz", "1", self.a010.pk))

    def test_reportar_en_un_punto_del_mapa(self):
        resp = self.client.get(reverse("reportes:crear") + "?piso=ext&x=550&y=478&lugar=Canchas de fútbol")
        self.assertEqual(resp.context["form"]["ubicacion"].value(), "Canchas de fútbol")
        datos = {"titulo": "Arco roto", "categoria": self.cat.pk, "descripcion": "El arco norte está suelto",
                 "ubicacion": "Canchas de fútbol", "piso": "ext", "mapa_x": "550", "mapa_y": "478"}
        self.client.post(reverse("reportes:crear"), datos)
        reporte = Reporte.objects.get()
        self.assertEqual(reporte.punto_mapa(), ("ext", 550.0, 478.0))

    def test_reporte_en_sala_va_al_centro_de_la_sala(self):
        datos = {"titulo": "Luz", "categoria": self.cat.pk, "descripcion": "parpadea", "sala": self.a010.pk}
        self.client.post(reverse("reportes:crear"), datos)
        piso, x, y = Reporte.objects.get().punto_mapa()
        self.assertEqual(piso, "1")
        self.assertEqual((x, y), self.a010.centro())

    def test_apoyar_y_quitar_apoyo(self):
        r = Reporte.objects.create(titulo="Luz", descripcion="d", categoria=self.cat, ubicacion="x", autor=self.beto)
        url = reverse("reportes:apoyar", args=[r.pk])
        resp = self.client.post(url, HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(resp.json(), {"apoyos": 1, "yo": True})
        resp = self.client.post(url, HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(resp.json(), {"apoyos": 0, "yo": False})

    def test_apoyar_solo_con_post(self):
        r = Reporte.objects.create(titulo="Luz", descripcion="d", categoria=self.cat, ubicacion="x", autor=self.beto)
        self.assertEqual(self.client.get(reverse("reportes:apoyar", args=[r.pk])).status_code, 405)

    def test_detalle_muestra_apoyos_y_enlace_al_mapa(self):
        r = Reporte.objects.create(titulo="Luz", descripcion="d", categoria=self.cat, sala=self.a010,
                                   ubicacion="A010", autor=self.beto)
        self.client.post(reverse("reportes:apoyar", args=[r.pk]))
        resp = self.client.get(reverse("reportes:detalle", args=[r.pk]))
        self.assertContains(resp, "1 apoyo")
        self.assertContains(resp, f"?reporte={r.pk}")

    def test_entrar_lleva_al_mapa(self):
        self.assertRedirects(self.client.get(reverse("bienvenida")), reverse("reportes:mapa"),
                             fetch_redirect_response=False)

    def test_archivos_del_mapa_completos(self):
        # el mapa necesita su codigo y sus estilos; si alguno queda vacio, la pagina sale en blanco
        from pathlib import Path
        carpeta = Path(__file__).resolve().parent / "static" / "mi_app" / "mapa"
        self.assertIn("function leerDato", (carpeta / "mapa.js").read_text(encoding="utf-8"))
        self.assertGreater((carpeta / "mapa.css").stat().st_size, 10000)
        # el mapa no usa transicion de pagina: sacar la foto del mapa al salir demoraba casi un segundo
        self.assertNotIn("@view-transition", (carpeta / "mapa.css").read_text(encoding="utf-8"))
        # burbujita con los reportes de cada piso
        self.assertIn("function burbujas", (carpeta / "mapa.js").read_text(encoding="utf-8"))

    def test_reporte_en_pasillo_va_a_su_piso(self):
        # un reporte en un punto sin sala (pasillo) tambien se dibuja en su piso
        datos = {"titulo": "Silla rota", "categoria": self.cat.pk, "descripcion": "en el pasillo",
                 "ubicacion": "Pasillo o espacio común ·  · Piso 3", "piso": "3", "mapa_x": "275", "mapa_y": "600"}
        self.client.post(reverse("reportes:crear"), datos)
        self.assertEqual(Reporte.objects.get().ubicacion, "Pasillo o espacio común · Piso 3")
        rep = self.client.get(reverse("reportes:mapa")).context["reportes"][0]
        self.assertEqual((rep["f"], rep["x"], rep["salapk"]), ("3", 275.0, None))

    def test_punto_del_mapa_con_numeros_raros(self):
        # si la direccion trae un punto que no es numero, el formulario lo ignora en vez de fallar
        resp = self.client.get(reverse("reportes:crear") + "?piso=ext&x=abc&y=&lugar=Cancha")
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.context["form"]["mapa_x"].value())

    def test_paginas_comprimidas(self):
        # el mapa viaja comprimido (pesa mucho menos por internet)
        resp = self.client.get(reverse("reportes:mapa"), HTTP_ACCEPT_ENCODING="gzip")
        self.assertEqual(resp.get("Content-Encoding"), "gzip")


class TokenDeSeguridadTests(TestCase):
    """si una pagina queda vieja, el formulario ya no da el error 'prohibido (403)' en ingles"""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user("eva@usm.cl", "eva@usm.cl", "clave-segura-123")
        self.cliente = Client(enforce_csrf_checks=True)
        self.cliente.login(username="eva@usm.cl", password="clave-segura-123")

    def test_token_de_la_cookie_sirve(self):
        # el script de la pagina copia el token de la cookie al formulario antes de enviarlo
        self.cliente.get(reverse("reportes:perfil"))
        token = self.cliente.cookies["csrftoken"].value
        resp = self.cliente.post(reverse("logout"), {"csrfmiddlewaretoken": token})
        self.assertEqual(resp.status_code, 302)

    def test_token_viejo_muestra_pagina_en_espanol(self):
        self.cliente.get(reverse("reportes:perfil"))
        resp = self.cliente.post(reverse("logout"), {"csrfmiddlewaretoken": "x" * 64})
        self.assertEqual(resp.status_code, 403)
        self.assertContains(resp, "Intenta de nuevo", status_code=403)

    def test_base_actualiza_el_token_al_enviar(self):
        resp = self.cliente.get(reverse("reportes:perfil"))
        self.assertContains(resp, 'input[name="csrfmiddlewaretoken"]')


class EncargadoTests(TestCase):
    """paso 7: el encargado cambia el estado con un comentario, queda en el historial y se avisa por correo"""

    def setUp(self):
        User = get_user_model()
        self.ana = User.objects.create_user("ana@usm.cl", "ana@usm.cl", "clave-segura-123", first_name="Ana")
        self.enc = User.objects.create_user("enc@usm.cl", "enc@usm.cl", "clave-segura-123", first_name="Andrés")
        Perfil.objects.create(usuario=self.enc, rol=Perfil.Rol.ENCARGADO)
        self.reporte = Reporte.objects.create(
            titulo="Luz", descripcion="d", categoria=Categoria.objects.get(nombre="Iluminación"),
            sala=Sala.objects.get(nombre="A010"), ubicacion="A010", autor=self.ana,
        )
        self.url = reverse("reportes:cambiar_estado", args=[self.reporte.pk])

    def test_estudiante_no_puede_cambiar_estado(self):
        self.client.login(username="ana@usm.cl", password="clave-segura-123")
        resp = self.client.post(self.url, {"estado": "resuelto", "comentario": "listo"})
        self.assertEqual(resp.status_code, 403)
        self.reporte.refresh_from_db()
        self.assertEqual(self.reporte.estado, Reporte.Estado.PENDIENTE)
        # y no ve el formulario
        self.assertNotContains(self.client.get(reverse("reportes:detalle", args=[self.reporte.pk])), "Actualizar estado")

    def test_encargado_cambia_estado_y_queda_historial(self):
        self.client.login(username="enc@usm.cl", password="clave-segura-123")
        self.assertContains(self.client.get(reverse("reportes:detalle", args=[self.reporte.pk])), "Actualizar estado")
        resp = self.client.post(self.url, {"estado": "en_proceso", "comentario": "Pedimos la ampolleta"})
        self.assertRedirects(resp, reverse("reportes:detalle", args=[self.reporte.pk]))
        self.reporte.refresh_from_db()
        self.assertEqual(self.reporte.estado, Reporte.Estado.EN_PROCESO)
        s = self.reporte.seguimientos.get()
        self.assertEqual((s.estado_anterior, s.estado_nuevo, s.autor), ("pendiente", "en_proceso", self.enc))
        # quien lo reporto recibe un correo y ve el comentario en el reporte
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ana@usm.cl"])
        self.assertIn("Pedimos la ampolleta", mail.outbox[0].body)
        self.client.login(username="ana@usm.cl", password="clave-segura-123")
        self.assertContains(self.client.get(reverse("reportes:detalle", args=[self.reporte.pk])), "Pedimos la ampolleta")

    def test_comentario_obligatorio(self):
        self.client.login(username="enc@usm.cl", password="clave-segura-123")
        resp = self.client.post(self.url, {"estado": "resuelto", "comentario": "   "})
        self.assertEqual(resp.status_code, 400)
        self.assertContains(resp, "Escribe qué se hizo", status_code=400)
        self.assertFalse(self.reporte.seguimientos.exists())

    def test_cambio_desde_el_admin_queda_en_historial(self):
        admin_ = get_user_model().objects.create_superuser("jefe", "jefe@usm.cl", "clave-segura-123")
        self.client.force_login(admin_)
        url = reverse("admin:mi_app_reporte_change", args=[self.reporte.pk])
        datos = {
            "titulo": "Luz", "descripcion": "d", "categoria": self.reporte.categoria_id, "sala": self.reporte.sala_id,
            "ubicacion": "A010", "estado": "resuelto", "autor": self.ana.pk, "piso": "", "mapa_x": "", "mapa_y": "",
            "latitud": "", "longitud": "",
            "seguimientos-TOTAL_FORMS": "0", "seguimientos-INITIAL_FORMS": "0",
        }
        self.client.post(url, datos)
        self.assertEqual(self.reporte.seguimientos.get().estado_nuevo, "resuelto")


class DatosDemoTests(TestCase):
    """comando para llenar el mapa con reportes de ejemplo"""

    def test_crea_y_borra_datos_de_ejemplo(self):
        from django.core.management import call_command
        call_command("datos_demo", stdout=StringIO())
        self.assertEqual(Reporte.objects.filter(autor__username__endswith="@usm.cl").count(), 18)
        self.assertTrue(Seguimiento.objects.exists())
        # todos con lugar en el mapa
        self.assertTrue(all(r.punto_mapa() for r in Reporte.objects.all()))
        call_command("datos_demo", stdout=StringIO())  # la segunda vez no duplica
        self.assertEqual(Reporte.objects.count(), 18)
        call_command("datos_demo", "--borrar", stdout=StringIO())
        self.assertEqual(Reporte.objects.count(), 0)


class TutorialTests(TestCase):
    """paso 8: tutorial del mapa la primera vez y se puede ver de nuevo desde mi perfil"""

    def test_mapa_trae_el_tutorial(self):
        carpeta = Path(__file__).resolve().parent / "static" / "mi_app" / "mapa"
        js = (carpeta / "mapa.js").read_text(encoding="utf-8")
        self.assertIn("upin_tutorial_v1", js)
        self.assertIn("Gestos en tu", js)
        self.assertIn(".tuto-card", (carpeta / "mapa.css").read_text(encoding="utf-8"))

    def test_perfil_enlaza_al_tutorial(self):
        get_user_model().objects.create_user("eva@usm.cl", "eva@usm.cl", "clave-segura-123")
        self.client.login(username="eva@usm.cl", password="clave-segura-123")
        self.assertContains(self.client.get(reverse("reportes:perfil")), "?tutorial=1")


class ArreglosFelipeTests(TestCase):
    """contraseñas con reglas claras, correo que no se cae y ubicacion sin preguntar siempre"""

    datos = {"nombre": "Ana", "apellido": "Pérez", "correo": "ana.perez@usm.cl"}

    def registrar(self, clave, repetir=None):
        return self.client.post(reverse("registro"), {**self.datos, "password1": clave, "password2": repetir or clave})

    def test_contraseña_sin_numeros(self):
        resp = self.registrar("solamenteletras")
        self.assertContains(resp, "al menos una letra y un número")

    def test_contraseña_sin_letras(self):
        resp = self.registrar("84736251")
        self.assertContains(resp, "al menos una letra y un número")

    def test_contraseña_corta(self):
        resp = self.registrar("ab12")
        self.assertContains(resp, "8 caracteres")

    def test_contraseña_buena(self):
        resp = self.registrar("campus-2026-k")
        self.assertRedirects(resp, reverse("verificar"))

    def test_se_muestran_las_reglas(self):
        self.assertContains(self.client.get(reverse("registro")), "Mínimo 8 caracteres")

    def test_si_falla_el_correo_no_se_cae(self):
        from unittest import mock
        with mock.patch("mi_app.views.send_mail", side_effect=OSError("sin internet")):
            resp = self.registrar("campus-2026-k")
        self.assertRedirects(resp, reverse("verificar"))

    def test_ubicacion_solo_con_permiso_previo(self):
        js = (Path(__file__).resolve().parent / "static" / "mi_app" / "mapa" / "mapa.js").read_text(encoding="utf-8")
        self.assertIn("permissions.query({name:'geolocation'})", js)
        self.assertNotIn("try{if('geolocation' in navigator&&window.isSecureContext)gpsBtn.click()}", js)
