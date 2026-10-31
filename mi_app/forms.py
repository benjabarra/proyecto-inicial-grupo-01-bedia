import os
from io import BytesIO

from django import forms
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

from .models import Reporte

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
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # la foto es obligatoria al crear un reporte
        self.fields["foto"].required = True
        self.fields["foto"].widget.attrs["accept"] = "image/*"

    def clean_foto(self):
        foto = self.cleaned_data.get("foto")
        if foto and foto.size > MAX_MB * 1024 * 1024:
            raise forms.ValidationError(f"La foto pesa mas de {MAX_MB} MB.")
        if foto and hasattr(foto, "image"):  # foto nueva (no una ya guardada)
            return reducir_imagen(foto)
        return foto
