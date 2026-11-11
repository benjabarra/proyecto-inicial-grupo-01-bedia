# datos que reciben todas las paginas: colores de la universidad, iniciales y rol
from types import SimpleNamespace

from .models import Campus, Universidad, iniciales, rol_de, universidad_para_correo

# tema por defecto (antes de elegir universidad): colores de u-pin
TEMA_UPIN = SimpleNamespace(
    sigla="U-Pin",
    nombre="",
    campus="",
    color_primario="#1D1D1F",
    color_acento="#FFC72C",
    imagen="",
)


def tema(request):
    """tema de la pagina: el de la universidad del usuario (o la elegida), o el de u-pin"""
    usuario = getattr(request, "user", None)
    uni = None
    datos = {}
    campus = None
    if usuario is not None and usuario.is_authenticated:
        uni = universidad_para_correo(usuario.email or usuario.username)
        datos = {"iniciales": iniciales(usuario), "rol": rol_de(usuario)}
        perfil = getattr(usuario, "perfil", None)
        campus = perfil.campus if perfil else None
    elif hasattr(request, "session") and request.session.get("universidad_id"):
        uni = Universidad.objects.filter(pk=request.session["universidad_id"]).first()
        campus = Campus.objects.filter(pk=request.session.get("campus_id")).first()
    return {"tema": uni or TEMA_UPIN, "campus_actual": campus, **datos}
