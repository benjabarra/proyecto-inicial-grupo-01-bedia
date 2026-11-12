# vistas de u-pin: cada funcion responde a una direccion de la pagina
from django.contrib import messages
from django.contrib.auth import get_user_model, login
import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db.models import Count, Exists, OuterRef, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.middleware.csrf import get_token
from django.templatetags.static import static
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import escape
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import CodigoForm, EntrarForm, EstadoForm, RegistroForm, ReporteForm
from .models import (
    CLAVE_CATEGORIA,
    Apoyo,
    Campus,
    Perfil,
    Reporte,
    Sala,
    Seguimiento,
    Universidad,
    puede_gestionar,
    rol_de,
    universidad_para_correo,
)

BACKEND = "django.contrib.auth.backends.ModelBackend"  # forma normal de iniciar sesion de django


# ---------- bienvenida y cuentas ----------

# portada: elegir universidad y campus antes de entrar.
# si ya inicio sesion, va directo al mapa
# fotos que van pasando en la portada (computador). uni = sigla de la universidad;
# campus = nombre exacto del campus o "" si la foto es de la universidad en general.
# la primera de cada campus es la principal
FOTOS_PORTADA = [
    ("usm-san-joaquin.jpg", "USM", "Campus San Joaquín"),
    ("portada/usm-san-joaquin-patio.jpg", "USM", "Campus San Joaquín"),
    ("portada/usm-casa-central.jpg", "USM", "Casa Central"),
    ("portada/usm-casa-central-torre.jpg", "USM", "Casa Central"),
    ("portada/usm-edificio-dorado.jpg", "USM", ""),
    ("portada/usm-campus-aereo.jpg", "USM", ""),
    ("portada/usm-jardines.jpg", "USM", ""),
    ("portada/usm-sede.jpg", "USM", ""),
]


def _fotos_portada():
    """lista para el carrusel de la portada: direccion de la foto, universidad, campus y texto del lugar"""
    return [
        {
            "src": static("mi_app/img/" + archivo),
            "uni": uni,
            "campus": campus,
            "lugar": f"{uni} · {campus}" if campus else "Universidad Técnica Federico Santa María",
        }
        for archivo, uni, campus in FOTOS_PORTADA
    ]


def bienvenida(request):
    if request.user.is_authenticated:
        return redirect("reportes:mapa")
    if request.method == "POST":
        campus = (
            Campus.objects.select_related("universidad")
            .filter(pk=request.POST.get("campus"), activo=True, universidad__activa=True)
            .first()
        )
        if campus:
            request.session["universidad_id"] = campus.universidad_id
            request.session["campus_id"] = campus.pk
            return redirect("login")
        error = "Elige tu campus para continuar."
    else:
        error = None
    universidades = Universidad.objects.prefetch_related("campus_set").order_by("-activa", "pk")
    return render(
        request,
        "bienvenida.html",
        {"universidades": universidades, "error": error, "fotos": _fotos_portada()},
    )


# guarda en el perfil el campus elegido en la portada
def _guardar_campus(request, usuario):
    """si eligio campus en la bienvenida y su perfil no tiene, se lo guardamos"""
    perfil = getattr(usuario, "perfil", None)
    campus_id = request.session.get("campus_id")
    if perfil and campus_id and perfil.campus_id is None:
        campus = Campus.objects.filter(pk=campus_id, activo=True).first()
        if campus:
            perfil.campus = campus
            perfil.save(update_fields=["campus"])


# crea el codigo de verificacion y lo manda por correo
def enviar_codigo(usuario):
    """crea un codigo nuevo y lo manda al correo (en desarrollo tambien sale en la terminal)"""
    perfil, _ = Perfil.objects.get_or_create(
        usuario=usuario,
        defaults={"universidad": universidad_para_correo(usuario.email)},
    )
    codigo = perfil.nuevo_codigo()
    if settings.DEBUG:
        # en desarrollo el codigo siempre queda en la terminal: si el correo se demora, igual se puede entrar
        print(f"\n[u-pin] codigo de {usuario.email}: {codigo}\n", flush=True)
    texto = (
        f"Hola {usuario.first_name or ''}.\n\n"
        f"Tu código para entrar a U-Pin es: {codigo}\n\n"
        f"Vence en {Perfil.MINUTOS_CODIGO} minutos. Si no fuiste tú, ignora este correo."
    )
    # version con formato (los correos solo de texto plano llegan mas seguido a spam)
    html = (
        '<div style="font-family:Arial,sans-serif;max-width:420px;margin:auto;color:#1B1A17">'
        f'<p>Hola {escape(usuario.first_name or "")},</p>'
        "<p>Tu código para entrar a <b>U-Pin</b> es:</p>"
        f'<p style="font-size:30px;font-weight:bold;letter-spacing:6px;background:#FFF4D0;'
        f'border-radius:12px;padding:14px;text-align:center">{codigo}</p>'
        f"<p>Vence en {Perfil.MINUTOS_CODIGO} minutos. Si no fuiste tú, ignora este correo.</p>"
        '<p style="color:#77746C;font-size:12px">U-Pin · reportes de infraestructura del campus</p></div>'
    )
    try:
        send_mail("Tu código de U-Pin: " + codigo, texto, None, [usuario.email], html_message=html)
    except Exception as error:  # correo mal configurado o sin internet: la pagina no se cae
        if settings.DEBUG:
            print(f"[u-pin] no se pudo enviar el correo ({error}).", flush=True)


# crear cuenta: solo con correo institucional.
# la cuenta queda inactiva hasta poner el codigo que llega al correo
def registro(request):
    if request.user.is_authenticated:
        return redirect("reportes:mapa")
    form = RegistroForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        datos = form.cleaned_data
        usuario = get_user_model().objects.create_user(
            username=datos["correo"],
            email=datos["correo"],
            password=datos["password1"],
            first_name=datos["nombre"].strip(),
            last_name=datos["apellido"].strip(),
            is_active=False,  # se activa al poner el codigo
        )
        campus = Campus.objects.filter(pk=request.session.get("campus_id"), activo=True).first()
        Perfil.objects.create(
            usuario=usuario, universidad=universidad_para_correo(datos["correo"]), campus=campus
        )
        enviar_codigo(usuario)
        request.session["verificar_id"] = usuario.pk
        return redirect("verificar")
    return render(request, "registration/registro.html", {"form": form})


# iniciar sesion con correo y contraseña. si falta verificar, pide el codigo
def entrar(request):
    if request.user.is_authenticated:
        return redirect("reportes:mapa")
    form = EntrarForm(request.POST or None)
    error = None
    if request.method == "POST" and form.is_valid():
        texto = form.cleaned_data["correo"].strip()
        usuario = (
            get_user_model()
            .objects.filter(Q(username__iexact=texto) | Q(email__iexact=texto))
            .first()
        )
        if usuario is None or not usuario.check_password(form.cleaned_data["password"]):
            error = "Correo o contraseña incorrectos."
        elif not usuario.is_active:
            # cuenta sin verificar: mandamos otro codigo si hace falta
            perfil = getattr(usuario, "perfil", None)
            if perfil is None or perfil.codigo_vencido():
                enviar_codigo(usuario)
            request.session["verificar_id"] = usuario.pk
            messages.info(request, "Primero confirma tu correo con el código que te enviamos.")
            return redirect("verificar")
        else:
            login(request, usuario, backend=BACKEND)
            _guardar_campus(request, usuario)
            siguiente = request.POST.get("next") or request.GET.get("next")
            if siguiente and url_has_allowed_host_and_scheme(siguiente, {request.get_host()}):
                return redirect(siguiente)
            return redirect("reportes:mapa")
    return render(
        request,
        "registration/login.html",
        {"form": form, "error": error, "next": request.GET.get("next", "")},
    )


# usuario que esta confirmando su correo (se guarda en la sesion)
def _usuario_por_verificar(request):
    pk = request.session.get("verificar_id")
    if not pk:
        return None
    return get_user_model().objects.filter(pk=pk, is_active=False).first()


# revisa el codigo de 6 numeros y activa la cuenta
def verificar(request):
    usuario = _usuario_por_verificar(request)
    if usuario is None:
        return redirect("login")
    perfil = usuario.perfil
    form = CodigoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if perfil.codigo_vencido():
            form.add_error("codigo", "El código venció. Pide uno nuevo.")
        elif perfil.intentos >= Perfil.MAX_INTENTOS:
            form.add_error("codigo", "Demasiados intentos. Pide un código nuevo.")
        elif form.cleaned_data["codigo"] != perfil.codigo:
            perfil.intentos += 1
            perfil.save(update_fields=["intentos"])
            form.add_error("codigo", "El código no coincide.")
        else:
            usuario.is_active = True
            usuario.save(update_fields=["is_active"])
            perfil.codigo = ""
            perfil.save(update_fields=["codigo"])
            request.session.pop("verificar_id", None)
            login(request, usuario, backend=BACKEND)
            _guardar_campus(request, usuario)
            messages.success(request, "¡Listo! Tu cuenta quedó confirmada.")
            return redirect("reportes:mapa")
    return render(
        request,
        "registration/verificar.html",
        {"form": form, "correo": usuario.email, "minutos": Perfil.MINUTOS_CODIGO},
    )


# manda otro codigo si paso al menos un minuto
@require_POST
def reenviar_codigo(request):
    usuario = _usuario_por_verificar(request)
    if usuario is None:
        return redirect("login")
    if usuario.perfil.puede_reenviar():
        enviar_codigo(usuario)
        messages.info(request, "Te enviamos un código nuevo.")
    else:
        messages.info(request, "Espera un minuto antes de pedir otro código.")
    return redirect("verificar")


# ---------- mapa ----------

# carpeta con los archivos fijos del mapa
DATOS = Path(__file__).resolve().parent / "datos"


@lru_cache
def _dato(nombre):
    """lee una vez los archivos fijos del mapa (edificios, arboles, canchas...)"""
    return json.loads((DATOS / nombre).read_text(encoding="utf-8"))


# agrega a cada reporte cuantos apoyos tiene y si yo lo apoye
def _con_apoyos(reportes, usuario):
    return reportes.annotate(
        n_apoyos=Count("apoyos", distinct=True),
        yo_apoyo=Exists(Apoyo.objects.filter(reporte=OuterRef("pk"), usuario=usuario)),
    )


def _pisos_del_mapa():
    """salas agrupadas por piso, con lo que el mapa necesita para dibujarlas"""
    pisos = {}
    for s in Sala.objects.select_related("edificio").order_by("pk"):
        sala = {
            "pk": s.pk,
            "pts": s.forma,
            "label": s.nombre,
            "building": s.edificio.nombre,
            "kind": s.extra.get("kind", "sala"),
        }
        sala.update({k: v for k, v in s.extra.items() if k != "kind"})
        pisos.setdefault(str(s.piso), []).append(sala)
    return pisos


# reportes en el formato que usa el mapa (posicion, color, estado, apoyos)
def _reportes_del_mapa(usuario):
    datos = []
    reportes = _con_apoyos(
        Reporte.objects.select_related("categoria", "sala__edificio"), usuario
    )
    for r in reportes:
        punto = r.punto_mapa()
        if punto is None:
            continue  # reportes antiguos sin lugar en el mapa: salen solo en la lista
        piso, x, y = punto
        datos.append(
            {
                "pk": r.pk,
                "t": r.titulo,
                "cat": CLAVE_CATEGORIA.get(r.categoria.nombre, "otro"),
                "e": r.estado,
                "f": piso,
                "x": x,
                "y": y,
                "b": r.sala.edificio.nombre if r.sala else "",
                "room": r.sala.nombre if r.sala else r.ubicacion.split(" · ")[0].strip(),
                "salapk": r.sala_id,
                "ap": r.n_apoyos,
                "yo": r.yo_apoyo,
                "url": reverse("reportes:detalle", args=[r.pk]),
                "urlApoyo": reverse("reportes:apoyar", args=[r.pk]),
            }
        )
    return datos


# pagina principal: el mapa del campus en 2.5d.
# le pasa al navegador las salas, los reportes y las direcciones para reportar y apoyar
@login_required
def mapa(request):

    return render(
        request,
        "reportes/mapa.html",
        {
            "escena": _dato("mapa_escena.json"),
            "grupos": _dato("mapa_grupos.json"),
            "pisos": _pisos_del_mapa(),
            "reportes": _reportes_del_mapa(request.user),
            "config": {
                "csrf": get_token(request),
                "urlCrear": reverse("reportes:crear"),
                "urlPerfil": reverse("reportes:perfil"),
                "suelo": static("mi_app/mapa/suelo.png"),
                "sueloHd": static("mi_app/mapa/suelo_hd.png"),
                "sueloMd": static("mi_app/mapa/suelo_md.png"),
            },
        },
    )


@login_required
@require_POST
def apoyar(request, pk):
    """'a mi tambien me pasa': si ya lo apoyaba, lo quita"""
    reporte = get_object_or_404(Reporte, pk=pk)
    apoyo, nuevo = Apoyo.objects.get_or_create(reporte=reporte, usuario=request.user)
    if not nuevo:
        apoyo.delete()
    if request.headers.get("X-Requested-With") == "fetch":
        return JsonResponse({"apoyos": reporte.apoyos.count(), "yo": nuevo})
    return redirect("reportes:detalle", pk=pk)


# ---------- reportes ----------

# lista de todos los reportes, con filtro de activos
@login_required
def lista_reportes(request):
    reportes = _con_apoyos(Reporte.objects.select_related("categoria", "autor"), request.user)
    filtro = request.GET.get("ver", "todos")
    if filtro == "activos":
        reportes = reportes.exclude(estado=Reporte.Estado.RESUELTO)
    return render(
        request,
        "reportes/lista.html",
        {"reportes": reportes, "titulo": "Reportes del campus", "hero": True, "filtro": filtro},
    )


# solo los reportes que hizo la persona
@login_required
def mis_reportes(request):
    reportes = _con_apoyos(
        Reporte.objects.filter(autor=request.user).select_related("categoria", "autor"), request.user
    )
    return render(
        request,
        "reportes/lista.html",
        {"reportes": reportes, "titulo": "Mis reportes", "filtro": "mios"},
    )


# formulario para un reporte nuevo.
# desde el mapa llega con la sala o el punto ya elegidos
@login_required
def crear_reporte(request):
    if request.method == "POST":
        form = ReporteForm(request.POST, request.FILES)
        if form.is_valid():
            reporte = form.save(commit=False)
            reporte.autor = request.user
            reporte.save()
            return redirect("reportes:detalle", pk=reporte.pk)
    else:
        # "reportar aqui" desde el mapa llega con ?sala=<id>, o con un punto: ?piso=&x=&y=&lugar=
        g = request.GET

        def numero(valor):
            # solo numeros validos para el punto del mapa (si llega algo raro, se ignora)
            try:
                return round(float(valor), 1)
            except (TypeError, ValueError):
                return None

        form = ReporteForm(
            initial={
                "sala": g.get("sala"),
                "piso": g.get("piso", "")[:4],
                "mapa_x": numero(g.get("x")),
                "mapa_y": numero(g.get("y")),
                "ubicacion": g.get("lugar", "")[:150],
            }
        )
    return render(request, "reportes/crear.html", {"form": form})


# pagina de un reporte con sus datos, apoyos, historial y enlace al mapa.
# el encargado ademas ve el formulario para cambiar el estado
@login_required
def detalle_reporte(request, pk, form_estado=None):
    reporte = get_object_or_404(Reporte.objects.select_related("sala__edificio", "autor"), pk=pk)
    gestiona = puede_gestionar(request.user)
    if gestiona and form_estado is None:
        form_estado = EstadoForm(initial={"estado": reporte.estado})
    return render(
        request,
        "reportes/detalle.html",
        {
            "reporte": reporte,
            "apoyos": reporte.apoyos.count(),
            "yo_apoyo": reporte.apoyos.filter(usuario=request.user).exists(),
            "en_mapa": reporte.punto_mapa() is not None,
            "seguimientos": reporte.seguimientos.select_related("autor"),
            "form_estado": form_estado if gestiona else None,
        },
        status=400 if form_estado is not None and form_estado.errors else 200,
    )


# el encargado cambia el estado de un reporte, deja un comentario y se le avisa por correo a quien lo reporto
@login_required
@require_POST
def cambiar_estado(request, pk):
    if not puede_gestionar(request.user):
        return HttpResponseForbidden("Solo un encargado puede cambiar el estado.")
    reporte = get_object_or_404(Reporte, pk=pk)
    form = EstadoForm(request.POST)
    if not form.is_valid():
        return detalle_reporte(request, pk, form_estado=form)
    anterior = reporte.estado
    reporte.estado = form.cleaned_data["estado"]
    reporte.save(update_fields=["estado", "actualizado"])
    seguimiento = Seguimiento.objects.create(
        reporte=reporte,
        autor=request.user,
        estado_anterior=anterior,
        estado_nuevo=reporte.estado,
        comentario=form.cleaned_data["comentario"],
    )
    _avisar_autor(request, seguimiento)
    messages.success(request, "Guardamos el cambio y le avisamos a quien lo reportó.")
    return redirect("reportes:detalle", pk=pk)


# correo para quien hizo el reporte cuando un encargado lo actualiza (si falla el correo, no se cae la pagina)
def _avisar_autor(request, seguimiento):
    reporte = seguimiento.reporte
    if not reporte.autor.email or reporte.autor == seguimiento.autor:
        return
    enlace = request.build_absolute_uri(reverse("reportes:detalle", args=[reporte.pk]))
    if seguimiento.cambio_estado():
        asunto = f"Tu reporte ahora está {reporte.get_estado_display().lower()}: {reporte.titulo}"
    else:
        asunto = f"Hay novedades en tu reporte: {reporte.titulo}"
    cuerpo = (
        f"Hola {reporte.autor.first_name or ''}".rstrip() + ",\n\n"
        f"Tu reporte \"{reporte.titulo}\" ({reporte.ubicacion}) está {reporte.get_estado_display().lower()}.\n\n"
        f"Comentario del encargado:\n{seguimiento.comentario}\n\n"
        f"Míralo aquí: {enlace}\n\nU-Pin"
    )
    send_mail(asunto, cuerpo, None, [reporte.autor.email], fail_silently=True)


# mi perfil: datos de la cuenta, cambiar campus y ver mis cifras
@login_required
def perfil(request):
    usuario = request.user
    # los administradores creados con createsuperuser no tienen perfil: lo creamos aqui
    perfil_, _ = Perfil.objects.get_or_create(
        usuario=usuario, defaults={"universidad": universidad_para_correo(usuario.email)}
    )
    if request.method == "POST":
        accion = request.POST.get("accion")
        if accion == "campus":
            campus = Campus.objects.filter(
                pk=request.POST.get("campus"), activo=True, universidad__activa=True
            ).first()
            if campus:
                perfil_.campus = campus
                perfil_.universidad = campus.universidad
                perfil_.save(update_fields=["campus", "universidad"])
                messages.success(request, "Cambiamos tu campus.")
        return redirect("reportes:perfil")
    mis = Reporte.objects.filter(autor=usuario)
    return render(
        request,
        "reportes/perfil.html",
        {
            "rol_nombre": Perfil.Rol(rol_de(usuario)).label,
            "total": mis.count(),
            "activos": mis.exclude(estado=Reporte.Estado.RESUELTO).count(),
            "resueltos": mis.filter(estado=Reporte.Estado.RESUELTO).count(),
            "apoyos_dados": Apoyo.objects.filter(usuario=usuario).count(),
            "recientes": mis.select_related("categoria")[:5],
            "campus_activos": Campus.objects.filter(activo=True, universidad__activa=True).select_related("universidad"),
        },
    )


# pagina que sale si falla la revision de seguridad (csrf) de un formulario.
# pasa cuando la pagina quedo vieja: en vez del error en ingles de django, se explica y se ofrece volver a intentar
def csrf_fallo(request, reason=""):
    return render(request, "reportes/csrf_fallo.html", status=403)
