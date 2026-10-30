# proyecto-inicial-grupo-01-bedia

## Ejecución local (Windows, PowerShell)

```powershell
git clone https://github.com/benjabarra/proyecto-inicial-grupo-01-bedia
cd proyecto-inicial-grupo-01-bedia
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Abrir http://127.0.0.1:8000/

## Datos para probar

1. Entrar a `/admin/` con el superusuario y crear al menos una **categoría** (obligatorio para crear reportes).
2. Crear un usuario de prueba en `/admin/` → Users → Add.
3. Iniciar sesión en `/`, ir a **Nuevo reporte**, enviarlo y revisar **Mis reportes** y **Todos los reportes**.
4. Cambiar el estado del reporte desde `/admin/` y comprobar que se actualiza.