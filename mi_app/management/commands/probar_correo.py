"""manda un correo de prueba para revisar que el correo de u-pin funciona.

uso:
    python manage.py probar_correo tu.nombre@usm.cl
"""
from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Manda un correo de prueba para revisar que el correo de U-Pin está bien configurado."

    def add_arguments(self, parser):
        parser.add_argument("correo", help="a quien mandarle el correo de prueba")

    def handle(self, *args, **opciones):
        if "smtp" not in settings.EMAIL_BACKEND:
            self.stdout.write(self.style.WARNING(
                "El correo NO está configurado: los códigos salen en esta terminal.\n"
                "Crea el archivo .env (copia .env.ejemplo) o agrega los secretos de Codespaces y vuelve a abrir la terminal."
            ))
            return
        self.stdout.write(f"Enviando desde {settings.EMAIL_HOST_USER} a {opciones['correo']}...")
        try:
            send_mail("Prueba de U-Pin", "Si te llegó este correo, los códigos de verificación funcionan.",
                      None, [opciones["correo"]])
        except Exception as error:
            self.stdout.write(self.style.ERROR(f"No se pudo enviar: {error}"))
            self.stdout.write("Revisa la contraseña de aplicación de Gmail (16 letras, sin espacios) y el correo.")
            return
        self.stdout.write(self.style.SUCCESS("Listo, revisa la bandeja de entrada (y spam)."))
