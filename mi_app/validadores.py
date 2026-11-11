# reglas extra para las contraseñas de u-pin (se suman a las de django en settings.py)
import re

from django.core.exceptions import ValidationError


class LetrasYNumerosValidator:
    """la contraseña tiene que tener al menos una letra y al menos un numero"""

    def validate(self, password, user=None):
        if not re.search(r"[^\W\d_]", password) or not re.search(r"\d", password):
            raise ValidationError(
                "La contraseña debe tener al menos una letra y un número.",
                code="password_sin_letras_y_numeros",
            )

    def get_help_text(self):
        return "Tu contraseña debe tener al menos una letra y un número."
