"""llena la base con reportes de ejemplo por todo el campus, para la presentacion.

uso:
    python manage.py datos_demo            crea cuentas y reportes de ejemplo
    python manage.py datos_demo --borrar   borra todo lo que creo este comando
"""
import json
from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files import File
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
# y, si tiene, el nombre de la foto
REPORTES = [
    (0, "El proyector no prende", "Se apaga a los pocos segundos de encenderlo. Tuvimos que hacer la clase sin presentación.",
     "Proyector y equipos", ("K", 3, "K303"), 6, 4,
     [(E, "Revisamos el equipo: falta el cable HDMI. Llega mañana."), ]),
    (1, "El aire acondicionado no funciona", "En la tarde la sala queda muy calurosa y no se puede estar.",
     "Climatización", ("K", 2, "K202"), 3, 5, []),
    (2, "El lavamanos no tiene agua", "En el baño de hombres el lavamanos no da agua aunque uno apriete la llave, no hay cómo lavarse las manos.",
     "Agua y goteras", ("B", 1, "Baños"), 9, 3,
     [(E, "Mantención va a revisar la llave de paso del baño.")], "lavamanos.jpg"),
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
    (3, "Puerta del baño sin manilla ni seguro", "A la puerta del cubículo le sacaron la manilla y el seguro, quedaron solo los agujeros y no se puede cerrar.",
     "Puertas, ventanas y cerraduras", ("K", 1, "Baño"), 7, 1,
     [(E, "Pedimos una manilla y un seguro nuevos al proveedor.")], "puerta_cerradura.jpg"),
    (4, "Gotera cuando llueve", "Cae agua del techo cerca de la puerta. Ya hay una mancha con hongos y el cielo se está soltando.",
     "Agua y goteras", ("K", -1, "KS110"), 8, 2, [], "gotera_techo.jpg"),
    (0, "Arco con la red rota", "La red del arco norte está rota y la pelota se pasa.",
     "Áreas verdes y exteriores", ("ext", "Canchas de fútbol"), 4, 4, []),
    (1, "Tablero de básquetbol quebrado", "En la cancha de básquetbol del gimnasio el vidrio del tablero está quebrado y caen pedazos a las graderías.",
     "Otro", ("F", 1, "Gimnasio"), 10, 3,
     [(E, "Mantención lo revisará el viernes. Mientras tanto no usen ese aro.")], "tablero_basquetbol.jpg"),
    (2, "Se cayeron planchas del cielo", "En el Testamento faltan varias planchas del cielo y se ve la estructura. Da miedo que se caiga otra.",
     "Daños en muro, techo o piso", ("F", 1, "Testamento"), 6, 2, [], "cielo_hall.jpg"),
    (3, "El ascensor se detiene entre pisos", "Se quedó detenido en el cuarto piso y el botón queda con la luz roja.",
     "Ascensor, escaleras y rampas", ("K", 4, "Ascensor"), 2, 5,
     [(E, "Se pidió revisión técnica urgente a la empresa del ascensor.")], "ascensor.jpg"),
    (4, "La pantalla del proyector no baja", "El motor de la pantalla suena pero no se mueve.",
     "Proyector y equipos", ("E", 2, "E201"), 14, 1,
     [(E, "Revisando el motor."), (R, "Se reparó el motor de la pantalla.")]),
    (0, "Sin red cableada en el departamento", "Los puntos de red de las oficinas no tienen conexión.",
     "Internet y WiFi", ("K", 5, "DINF"), 1, 0, []),
    (1, "Faltan luces en la entrada", "En la tarde la entrada del auditorio queda muy oscura.",
     "Iluminación", ("ext", "Auditorio"), 3, 2, []),
    (2, "Camarines sin agua caliente", "Las duchas de los camarines solo tienen agua fría.",
     "Agua y goteras", ("F", 1, "Gimnasio"), 5, 3, []),
    (3, "Estanque del WC trizado", "El estanque tiene una trizadura grande en la tapa y bota agua al tirar la cadena.",
     "Baños", ("K", 2, "Baño"), 2, 3, [], "estanque_bano.jpg"),
    (4, "Vidrios quebrados en el casino", "Varios vidrios del ventanal del casino están quebrados y pueden caer pedazos sobre las mesas.",
     "Puertas, ventanas y cerraduras", ("F", 1, "Casino"), 1, 5, [], "vidrios_quebrados.jpg"),
    (0, "Monitor quebrado en la B035", "La pantalla del computador está quebrada y no se ve nada, el puesto no se puede usar.",
     "Proyector y equipos", ("B", 1, "B035"), 3, 2,
     [(E, "Informática pidió un monitor de reemplazo.")], "monitor_roto.jpg"),
]

# fotos reales de problemas del campus tomadas por el equipo (carpeta mi_app/datos/fotos_demo)
FOTOS = Path(__file__).resolve().parents[2] / "datos" / "fotos_demo"


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
        for i, (autor, titulo, texto, categoria, lugar, dias, n_apoyos, historial, *foto) in enumerate(REPORTES):
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
            reporte = Reporte(**datos)
            if foto:
                with open(FOTOS / foto[0], "rb") as archivo:
                    reporte.foto.save(foto[0], File(archivo), save=False)
            reporte.save()
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
