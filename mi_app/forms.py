import os
from io import BytesIO

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

from .models import Reporte, Universidad, universidad_para_correo

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


class ReporteForm(forms.ModelForm):
    class Meta:
        model = Reporte
        fields = ["titulo", "categoria", "ubicacion", "descripcion", "foto"]
        labels = {
            "titulo": "Título",
            "categoria": "Categoría",
            "ubicacion": "Ubicación",
            "descripcion": "Descripción",
            "foto": "Foto de evidencia",
        }
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # la foto es obligatoria al crear un reporte
        self.fields["foto"].required = True
        self.fields["foto"].widget.attrs["accept"] = "image/*"

    def clean_foto(self):
        foto = self.cleaned_data.get("foto")
        if foto and foto.size > MAX_MB * 1024 * 1024:
            raise forms.ValidationError(f"La foto pesa más de {MAX_MB} MB.")
        if foto and hasattr(foto, "image"):  # foto nueva (no una ya guardada)
            return reducir_imagen(foto)
        return foto


class RegistroForm(forms.Form):
    nombre = forms.CharField(label="Nombre", max_length=150)
    correo = forms.EmailField(label="Correo institucional")
    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Repetir contraseña",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

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


class CodigoForm(forms.Form):
    codigo = forms.RegexField(
        label="Código de 6 dígitos",
        regex=r"^\d{6}$",
        error_messages={"invalid": "El código tiene 6 números."},
        widget=forms.TextInput(
            attrs={"inputmode": "numeric", "autocomplete": "one-time-code", "maxlength": 6}
        ),
    )
