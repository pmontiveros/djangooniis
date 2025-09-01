import os
from waitress import serve

# Ajusta al nombre de tu proyecto Django (el que contiene settings.py)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pocdashboard.settings")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

if __name__ == "__main__":
    print("🚀 Starting Waitress server at http://127.0.0.1:8000")
    serve(application, host="127.0.0.1", port=8000)