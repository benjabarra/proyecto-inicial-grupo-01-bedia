from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ReporteForm
from .models import Reporte


@login_required
def lista_reportes(request):
    reportes = Reporte.objects.select_related("categoria", "autor")
    return render(
        request,
        "reportes/lista.html",
        {"reportes": reportes, "titulo": "Reportes del campus"},
    )


@login_required
def mis_reportes(request):
    reportes = Reporte.objects.filter(autor=request.user).select_related("categoria", "autor")
    return render(
        request,
        "reportes/lista.html",
        {"reportes": reportes, "titulo": "Mis reportes"},
    )


@login_required
def crear_reporte(request):
    if request.method == "POST":
        form = ReporteForm(request.POST)
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