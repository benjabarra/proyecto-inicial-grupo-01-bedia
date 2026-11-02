from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import CodigoForm, EntrarForm, RegistroForm, ReporteForm
from .models import Perfil, Reporte, Universidad, universidad_para_correo

BACKEND = "django.contrib.auth.backends.ModelBackend"


# ---------- bienvenida y cuentas ----------

def bienvenida(request):
    if request.user.is_authenticated:
        return redirect("reportes:lista")
    universidades = Universidad.objects.all()
    if request.method == "POST":
        uni = universidades.filter(pk=request.POST.get("universidad")).first()
        if uni:
            request.session["universidad_id"] = uni.pk
            return redirect("login")
    return render(request, "bienvenida.html", {"universidades": universidades})


def enviar_codigo(usuario):
    """crea un codigo nuevo y lo manda al correo (en pruebas sale en la terminal)"""
    perfil, _ = Perfil.objects.get_or_create(
        usuario=usuario,
        defaults={"universidad": universidad_para_correo(usuario.email)},
    )
    codigo = perfil.nuevo_codigo()
    send_mail(
        "Tu código de U-Pin",
        f"Hola {usuario.first_name or ''}.\n\n"
        f"Tu código para entrar a U-Pin es: {codigo}\n\n"
        f"Vence en {Perfil.MINUTOS_CODIGO} minutos. Si no fuiste tú, ignora este correo.",
        None,
        [usuario.email],
    )


def registro(request):
    if request.user.is_authenticated:
        return redirect("reportes:lista")
    form = RegistroForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        datos = form.cleaned_data
        usuario = get_user_model().objects.create_user(
            username=datos["correo"],
            email=datos["correo"],
            password=datos["password1"],
            first_name=datos["nombre"],
            is_active=False,  # se activa al poner el codigo
        )
        Perfil.objects.create(usuario=usuario, universidad=universidad_para_correo(datos["correo"]))
        enviar_codigo(usuario)
        request.session["verificar_id"] = usuario.pk
        return redirect("verificar")
    return render(request, "registration/registro.html", {"form": form})


def entrar(request):
    if request.user.is_authenticated:
        return redirect("reportes:lista")
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
            siguiente = request.POST.get("next") or request.GET.get("next")
            if siguiente and url_has_allowed_host_and_scheme(siguiente, {request.get_host()}):
                return redirect(siguiente)
            return redirect("reportes:lista")
    return render(
        request,
        "registration/login.html",
        {"form": form, "error": error, "next": request.GET.get("next", "")},
    )


def _usuario_por_verificar(request):
    pk = request.session.get("verificar_id")
    if not pk:
        return None
    return get_user_model().objects.filter(pk=pk, is_active=False).first()


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
            messages.success(request, "¡Listo! Tu cuenta quedó confirmada.")
            return redirect("reportes:lista")
    return render(
        request,
        "registration/verificar.html",
        {"form": form, "correo": usuario.email, "minutos": Perfil.MINUTOS_CODIGO},
    )


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


# ---------- reportes ----------

@login_required
def lista_reportes(request):
    reportes = Reporte.objects.select_related("categoria", "autor")
    filtro = request.GET.get("ver", "todos")
    if filtro == "activos":
        reportes = reportes.exclude(estado=Reporte.Estado.RESUELTO)
    return render(
        request,
        "reportes/lista.html",
        {"reportes": reportes, "titulo": "Reportes del campus", "hero": True, "filtro": filtro},
    )


@login_required
def mis_reportes(request):
    reportes = Reporte.objects.filter(autor=request.user).select_related("categoria", "autor")
    return render(
        request,
        "reportes/lista.html",
        {"reportes": reportes, "titulo": "Mis reportes", "filtro": "mios"},
    )


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
        form = ReporteForm()
    return render(request, "reportes/crear.html", {"form": form})


@login_required
def detalle_reporte(request, pk):
    reporte = get_object_or_404(Reporte, pk=pk)
    return render(request, "reportes/detalle.html", {"reporte": reporte})
