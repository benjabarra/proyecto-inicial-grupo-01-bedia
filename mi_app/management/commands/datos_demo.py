"""llena la base con reportes de ejemplo por todo el campus, para la presentacion.

uso:
    python manage.py datos_demo            crea cuentas y reportes de ejemplo
    python manage.py datos_demo --borrar   borra todo lo que creo este comando
"""
import json
from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from mi_app.models import (
    Apoyo,
    Campus,
    Categoria,
    Perfil,
    Reporte,
    Sala,
    Seguimiento,
    universidad_para_correo,
)

CLAVE = "upin-demo-2026"  # contraseña de todas las cuentas de ejemplo (solo para la demo)

# cuentas de ejemplo: correo, nombre, apellido, rol
CUENTAS = [
    ("camila.rojas@usm.cl", "Camila", "Rojas", Perfil.Rol.ESTUDIANTE),
    ("matias.soto@usm.cl", "Matías", "Soto", Perfil.Rol.ESTUDIANTE),
    ("fernanda.diaz@usm.cl", "Fernanda", "Díaz", Perfil.Rol.ESTUDIANTE),
    ("tomas.munoz@usm.cl", "Tomás", "Muñoz", Perfil.Rol.ESTUDIANTE),
    ("javiera.lopez@usm.cl", "Javiera", "López", Perfil.Rol.ESTUDIANTE),
    ("encargado.demo@usm.cl", "Andrés", "Vidal", Perfil.Rol.ENCARGADO),
]

P, E, R = Reporte.Estado.PENDIENTE, Reporte.Estado.EN_PROCESO, Reporte.Estado.RESUELTO

# reportes: autor (indice de CUENTAS), titulo, descripcion, categoria,
# lugar (edificio, piso, sala) o ("ext", lugar exterior), dias atras, apoyos, historial [(estado, comentario)]
REPORTES = [
    (0, "El proyector no prende", "Se apaga a los pocos segundos de encenderlo. Tuvimos que hacer la clase sin presentación.",
     "Proyector y equipos", ("K", 3, "K303"), 6, 4,
     [(E, "Revisamos el equipo: falta el cable HDMI. Llega mañana."), ]),
    (1, "El aire acondicionado no funciona", "En la tarde la sala queda muy calurosa y no se puede estar.",
     "Climatización", ("K", 2, "K202"), 3, 5, []),
    (2, "No hay papel ni jabón", "Los dispensadores están vacíos desde el lunes.",
     "Baños", ("K", 3, "Baño"), 9, 3,
     [(E, "Le avisamos al equipo de aseo."), (R, "Se repuso el papel y el jabón en todos los baños del piso.")]),
    (3, "El WiFi se cae en la sala de estudio", "La red eduroam se desconecta cada pocos minutos en el sector de mesas.",
     "Internet y WiFi", ("F", 2, "Biblioteca"), 4, 5,
     [(E, "Informática instalará otra antena en el sector de mesas.")]),
    (4, "Basureros llenos después de almuerzo", "A las 14:00 ya no cabe nada y la basura queda en el suelo.",
     "Aseo y basura", ("F", 1, "Casino"), 2, 2, []),
    (0, "Sillas rotas al fondo de la sala", "Hay tres sillas con el respaldo suelto en la última fila.",
     "Mobiliario", ("A", 1, "A010"), 5, 1, []),
    (1, "Tubo fluorescente parpadea", "El tubo de la entrada parpadea y molesta mucho en clases.",
     "Iluminación", ("A", 2, "A212"), 12, 2,
     [(R, "Se cambió el tubo fluorescente.")]),
    (2, "Enchufes sin corriente", "Los enchufes de la fila de atrás no dan corriente, no podemos cargar los notebooks.",
     "Electricidad y enchufes", ("B", 1, "B021"), 1, 3, []),
    (3, "La puerta no cierra con llave", "La cerradura está trabada y la sala queda abierta en la noche.",
     "Puertas, ventanas y cerraduras", ("B", 1, "Sala LDS"), 7, 1,
     [(E, "Pedimos una cerradura nueva al proveedor.")]),
    (4, "Gotera cuando llueve", "Cae agua del techo cerca de la puerta, el piso queda resbaloso.",
     "Agua y goteras", ("K", -1, "KS110"), 8, 2, []),
    (0, "Arco con la red rota", "La red del arco norte está rota y la pelota se pasa.",
     "Áreas verdes y exteriores", ("ext", "Canchas de fútbol"), 4, 4, []),
    (1, "Tablero de básquetbol suelto", "El tablero se mueve cuando la pelota pega en el aro.",
     "Áreas verdes y exteriores", ("ext", "Básquetbol"), 10, 3,
     [(E, "Mantención lo revisará el viernes. Mientras tanto no usen ese aro.")]),
    (2, "Grieta en el muro", "Apareció una grieta larga en el muro junto a la ventana.",
     "Daños en muro, techo o piso", ("F", 4, "F404"), 6, 0, []),
    (3, "El ascensor se detiene entre pisos", "Se quedó parado unos segundos entre el piso 1 y el 2.",
     "Ascensor, escaleras y rampas", ("K", 1, "Ascensor"), 2, 5,
     [(E, "Se pidió revisión técnica urgente a la empresa del ascensor.")]),
    (4, "La pantalla del proyector no baja", "El motor de la pantalla suena pero no se mueve.",
     "Proyector y equipos", ("E", 2, "E201"), 14, 1,
     [(E, "Revisando el motor."), (R, "Se reparó el motor de la pantalla.")]),
    (0, "Sin red cableada en el departamento", "Los puntos de red de las oficinas no tienen conexión.",
     "Internet y WiFi", ("K", 5, "DINF"), 1, 0, []),
    (1, "Faltan luces en la entrada", "En la tarde la entrada del auditorio queda muy oscura.",
     "Iluminación", ("ext", "Auditorio"), 3, 2, []),
    (2, "Camarines sin agua caliente", "Las duchas de los camarines solo tienen agua fría.",
     "Agua y goteras", ("F", 1, "Gimnasio"), 5, 3, []),
]


def lugares_exteriores():
    """nombre -> (x, y) de los lugares exteriores del mapa"""
    escena = Path(__file__).resolve().parents[2] / "datos" / "mapa_escena.json"
    datos = json.loads(escena.read_text(encoding="utf-8"))
    return {nombre: (x, y) for nombre, x, y in datos["ground"]}


class Command(BaseCommand):
    help = "Crea cuentas y reportes de ejemplo para la demo (con --borrar los quita)."

    def add_arguments(self, parser):
        parser.add_argument("--borrar", action="store_true", help="borra las cuentas y reportes de ejemplo")

    @transaction.atomic
    def handle(self, *args, **opciones):
        User = get_user_model()
        correos = [c[0] for c in CUENTAS]
        if opciones["borrar"]:
            n = Reporte.objects.filter(autor__username__in=correos).count()
            User.objects.filter(username__in=correos).delete()  # borra tambien sus reportes y apoyos
            self.stdout.write(self.style.SUCCESS(f"Listo: se borraron las cuentas de ejemplo y {n} reportes."))
            return
        if Reporte.objects.filter(autor__username__in=correos).exists():
            self.stdout.write("Los datos de ejemplo ya están. Para crearlos de nuevo: python manage.py datos_demo --borrar")
            return

        # cuentas (ya confirmadas, con su universidad y campus)
        campus = Campus.objects.filter(nombre__icontains="San Joaqu").first()
        usuarios = []
        for correo, nombre, apellido, rol in CUENTAS:
            u, _ = User.objects.get_or_create(username=correo, defaults={"email": correo})
            u.email, u.first_name, u.last_name, u.is_active = correo, nombre, apellido, True
            u.set_password(CLAVE)
            u.save()
            Perfil.objects.update_or_create(
                usuario=u,
                defaults={"rol": rol, "universidad": universidad_para_correo(correo), "campus": campus},
            )
            usuarios.append(u)
        encargado = usuarios[-1]
        estudiantes = usuarios[:-1]

        exteriores = lugares_exteriores()
        ahora = timezone.now()
        creados, saltados = 0, []
        for i, (autor, titulo, texto, categoria, lugar, dias, n_apoyos, historial) in enumerate(REPORTES):
            datos = {
                "titulo": titulo,
                "descripcion": texto,
                "categoria": Categoria.objects.get_or_create(nombre=categoria)[0],
                "autor": estudiantes[autor],
            }
            if lugar[0] == "ext":
                if lugar[1] not in exteriores:
                    saltados.append(titulo)
                    continue
                x, y = exteriores[lugar[1]]
                # un poco corrido para que no quede justo encima del nombre del lugar
                datos.update(piso="ext", mapa_x=x + 18, mapa_y=y + 14, ubicacion=f"{lugar[1]} · Exterior del campus")
            else:
                letra, piso, nombre = lugar
                sala = Sala.objects.filter(edificio__letra=letra, piso=piso, nombre=nombre).first()
                if not sala:
                    saltados.append(titulo)
                    continue
                datos.update(sala=sala, piso=str(sala.piso), ubicacion=str(sala)[:150])
            reporte = Reporte.objects.create(**datos)
            # fecha en el pasado (unas horas distinta para cada uno)
            creado = ahora - timedelta(days=dias, hours=(i * 5) % 9)
            estado = Reporte.Estado.PENDIENTE
            # cada paso del historial, uno o dos dias despues del anterior
            fecha = creado
            for nuevo, comentario in historial:
                fecha = min(fecha + timedelta(days=1, hours=2), ahora - timedelta(minutes=30))
                s = Seguimiento.objects.create(
                    reporte=reporte, autor=encargado, estado_anterior=estado, estado_nuevo=nuevo, comentario=comentario
                )
                Seguimiento.objects.filter(pk=s.pk).update(creado=fecha)
                estado = nuevo
            Reporte.objects.filter(pk=reporte.pk).update(creado=creado, actualizado=fecha, estado=estado)
            # apoyos de otras cuentas de ejemplo
            otros = [u for u in estudiantes if u != estudiantes[autor]]
            Apoyo.objects.bulk_create(Apoyo(reporte=reporte, usuario=u) for u in otros[:n_apoyos])
            creados += 1

        self.stdout.write(self.style.SUCCESS(f"Listo: {creados} reportes de ejemplo en el campus."))
        if saltados:
            self.stdout.write(f"No se encontró el lugar de: {', '.join(saltados)}")
        self.stdout.write(f"Cuentas de ejemplo (contraseña {CLAVE}):")
        for correo, nombre, apellido, rol in CUENTAS:
            self.stdout.write(f"  {correo}  ·  {nombre} {apellido}  ·  {rol.label}")
