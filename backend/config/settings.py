"""Ajustes de Django para BLENS.

Todo lo sensible o dependiente del entorno se lee de variables de entorno (§15: sin
secretos en el repo). En AWS las provee Secrets Manager; en local, un `.env` que no
se versiona (ver `.env.example`).
"""

import os
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
REPO_DIR = BASE_DIR.parent


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(int(default))).lower() in ("1", "true", "yes", "on")


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-inseguro-no-usar-en-produccion")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [
    h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h
]

#: Orígenes desde los que se aceptan peticiones con sesión. El frontend **no comparte
#: origen con la API**: en desarrollo vive en el servidor de Vite y en producción en
#: CloudFront, así que sin esto toda escritura autenticada se queda en un 403 de CSRF.
#: Los valores por defecto son los puertos de desarrollo del proyecto; en AWS lo fija
#: la variable de entorno con el dominio real.
CSRF_TRUSTED_ORIGINS = [
    o
    for o in os.environ.get(
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        "http://localhost:5177,http://127.0.0.1:5177" if DEBUG else "",
    ).split(",")
    if o
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # BLENS
    "apps.tenancy",
    "apps.catalog",
    "apps.compliance",
    "apps.profiling",
    "apps.documents",
    "apps.evidence",
    "apps.risk",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

# --- Base de datos -------------------------------------------------------------
# En producción, Aurora PostgreSQL (§5). En local, el contenedor de docker-compose.
_db = urlparse(os.environ.get("DATABASE_URL", "postgres://blens:blens@localhost:5434/blens_dev"))
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _db.path.lstrip("/"),
        "USER": _db.username or "",
        "PASSWORD": _db.password or "",
        "HOST": _db.hostname or "",
        "PORT": str(_db.port or ""),
        "CONN_MAX_AGE": 60,
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Internacionalización ------------------------------------------------------
LANGUAGE_CODE = "es-es"
TIME_ZONE = "Europe/Madrid"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Ficheros generados (PDF de categorización y DdA). En AWS van a S3 con versioning y
# Object Lock (§11); en local, al disco.
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- Celery (§5: trabajo pesado fuera del ciclo request/response) --------------
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-1")
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6381/0")
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_EAGER_PROPAGATES = env_bool("CELERY_TASK_EAGER_PROPAGATES", False)
CELERY_BROKER_TRANSPORT_OPTIONS = {"region": AWS_REGION}
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE

# --- Seguridad (BLENS aspira a ENS Alto, §13) ---------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
