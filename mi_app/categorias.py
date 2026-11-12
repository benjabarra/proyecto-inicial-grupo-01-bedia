# color e icono de cada categoria, los mismos que usa el mapa (mapa.js, lista CATS).
# asi la lista de reportes se ve igual dentro y fuera del mapa
from types import SimpleNamespace

from .models import CLAVE_CATEGORIA

_DATOS = {
    "bano": ("#0C8599", "M6 3h5v7H6z M4 10h14v1a6 6 0 0 1-6 6h-3l-1 4h7"),
    "agua": ("#1C7ED6", "M12 3s6 6.2 6 10.5a6 6 0 0 1-12 0C6 9.2 12 3 12 3z"),
    "clima": ("#E8590C", "M10 13.5V5a2 2 0 0 1 4 0v8.5a4 4 0 1 1-4 0z M12 9v7"),
    "luz": ("#F59F00", "M9.5 18h5 M10 21h4 M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z"),
    "elec": ("#7048E8", "M13 3L5 14h6l-1 7 8-11h-6l1-7z"),
    "wifi": ("#364FC7", "M2.5 9a14 14 0 0 1 19 0 M5.5 12.5a9.5 9.5 0 0 1 13 0 M8.8 16a5 5 0 0 1 6.4 0 M12 19.5h.01"),
    "equipo": ("#AE3EC9", "M3 4h18v12H3z M8 20h8 M12 16v4"),
    "mueble": ("#8D5524", "M7 3h10v9H7z M5 12h14 M8 12v9 M16 12v9"),
    "puerta": ("#D6336C", "M6 3h12v18H6z M14.5 12h.01 M3 21h18"),
    "danos": ("#C92A2A", "M4 4h16v16H4z M12 4l-2 5 3 3-2 4 1 4"),
    "aseo": ("#2B8A3E", "M4 7h16 M9 7V4h6v3 M6 7l1 14h10l1-14 M10 11v6 M14 11v6"),
    "verde": ("#5C940D", "M12 21v-6 M12 3a5 5 0 0 0-5 5 4 4 0 0 0 1 7h8a4 4 0 0 0 1-7 5 5 0 0 0-5-5z"),
    "ascensor": ("#495057", "M3 20h5v-4h4v-4h4V8h5"),
    "otro": ("#868E96", "M6 12h.01 M12 12h.01 M18 12h.01"),
}

ORDEN_CATEGORIAS = list(_DATOS)  # orden de los chips, igual que en el mapa


def visual(nombre_categoria):
    """clave, color e icono (trazo svg de 24x24) de una categoria"""
    clave = CLAVE_CATEGORIA.get(nombre_categoria, "otro")
    color, icono = _DATOS.get(clave, _DATOS["otro"])
    return SimpleNamespace(clave=clave, color=color, icono=icono)
