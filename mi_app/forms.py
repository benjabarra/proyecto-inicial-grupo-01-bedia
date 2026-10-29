from django import forms
from .models import Reporte


class ReporteForm(forms.ModelForm):
    class Meta:
        model = Reporte
        fields = ["titulo", "categoria", "ubicacion", "descripcion"]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 4})}
