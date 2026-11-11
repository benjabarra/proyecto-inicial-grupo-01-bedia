# formularios de u-pin: revisan lo que escribe la persona antes de guardarlo
import os
from io import BytesIO

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

from .models import Reporte, Sala, Universidad, universidad_para_correo

# tamaño maximo de la foto y lado maximo despues de achicarla
MAX_MB = 8
LADO_MAX = 1280


def reducir_imagen(archivo):
    """achica la foto y la guarda como jpg para que pese poco"""
    img = ImageOps.exif_transpose(Image.open(archivo)).convert("RGB")
    img.thumbnail((LADO_MAX, LADO_MAX))
    buffer = BytesIO()
    img.save(buffer, "JPEG", quality=80, optimize=True)
    nombre = os.path.splitext(os.path.basename(archivo.name))[0] + ".jpg"
    return ContentFile(buffer.getvalue(), name=nombre)


# formulario de un reporte nuevo
class ReporteForm(forms.ModelForm):
    class Meta:
        model = Reporte
        fields = ["titulo", "categoria", "sala", "ubicacion", "descripcion", "foto", "piso", "mapa_x", "mapa_y"]
        labels = {
            "titulo": "Título",
            "categoria": "Categoría",
            "sala": "Sala o lugar",
            "ubicacion": "Detalle de la ubicación",
            "descripcion": "Descripción",
            "foto": "Foto de evidencia",
        }
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 4}),
            # el punto del mapa viaja escondido desde "Reportar aquí"
            "piso": forms.HiddenInput,
            "mapa_x": forms.HiddenInput,
            "mapa_y": forms.HiddenInput,
        }

    # ajusta los campos: foto opcional y lista de salas ordenada
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # la foto es opcional, pero ayuda al encargado a encontrar el problema
        self.fields["foto"].required = False
        self.fields["foto"].help_text = "Opcional. Evita fotografiar a personas."
        self.fields["foto"].widget.attrs["accept"] = "image/*"
        self.fields["sala"].queryset = (
            Sala.objects.exclude(nombre="").select_related("edificio").order_by("edificio__letra", "piso", "nombre")
        )
        self.fields["sala"].empty_label = "— No está en la lista —"
        self.fields["categoria"].empty_label = "— Elige una categoría —"
        self.fields["ubicacion"].required = False
        self.fields["ubicacion"].help_text = "Opcional si elegiste una sala. Ej: al fondo, junto a la ventana."

    # revisa que haya sala o detalle de ubicacion, y arma el texto de ubicacion
    def clean(self):
        datos = super().clean()
        sala, detalle = datos.get("sala"), (datos.get("ubicacion") or "").strip()
        # limpia separadores vacios (ej: "pasillo ·  · piso 3" -> "pasillo · piso 3")
        detalle = " · ".join(p.strip() for p in detalle.split("·") if p.strip())
        datos["ubicacion"] = detalle
        if not sala and not detalle:
            self.add_error("ubicacion", "Elige una sala o escribe dónde está el problema.")
        elif sala:
            datos["ubicacion"] = (f"{sala} · {detalle}" if detalle else str(sala))[:150]
            if datos.get("mapa_x") is None:
                datos["piso"] = str(sala.piso)
        return datos

    # revisa el peso de la foto y la achica
    def clean_foto(self):
        foto = self.cleaned_data.get("foto")
        if foto and foto.size > MAX_MB * 1024 * 1024:
            raise forms.ValidationError(f"La foto pesa más de {MAX_MB} MB.")
        if foto and hasattr(foto, "image"):  # foto nueva (no una ya guardada)
            return reducir_imagen(foto)
        return foto


# formulario de crear cuenta: nombre, apellido, correo institucional y contraseña
class RegistroForm(forms.Form):
    nombre = forms.CharField(label="Nombre", max_length=150, widget=forms.TextInput(attrs={"autocomplete": "given-name"}))
    apellido = forms.CharField(label="Apellido", max_length=150, widget=forms.TextInput(attrs={"autocomplete": "family-name"}))
    correo = forms.EmailField(label="Correo institucional")
    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Repetir contraseña",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    # solo correos institucionales y que no exista otra cuenta igual
    def clean_correo(self):
        correo = self.cleaned_data["correo"].strip().lower()
        if universidad_para_correo(correo) is None:
            dominios = ", ".join(f"@{u.dominio}" for u in Universidad.objects.all())
            raise forms.ValidationError(f"Usa tu correo institucional ({dominios}).")
        User = get_user_model()
        if (
            User.objects.filter(username__iexact=correo).exists()
            or User.objects.filter(email__iexact=correo).exists()
        ):
            raise forms.ValidationError("Ya existe una cuenta con ese correo.")
        return correo

    def clean(self):
        datos = super().clean()
        p1, p2 = datos.get("password1"), datos.get("password2")
        if p1 and p2:
            if p1 != p2:
                self.add_error("password2", "Las contraseñas no coinciden.")
            else:
                try:
                    validate_password(p1)
                except ValidationError as error:
                    self.add_error("password1", error)
        return datos


# formulario de iniciar sesion
class EntrarForm(forms.Form):
    correo = forms.CharField(
        label="Correo institucional",
        max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "username", "autofocus": True}),
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )


# formulario del codigo de 6 numeros
class CodigoForm(forms.Form):
    codigo = forms.RegexField(
        label="Código de 6 dígitos",
        regex=r"^\d{6}$",
        error_messages={"invalid": "El código tiene 6 números."},
        widget=forms.TextInput(
            attrs={"inputmode": "numeric", "autocomplete": "one-time-code", "maxlength": 6}
        ),
    )
