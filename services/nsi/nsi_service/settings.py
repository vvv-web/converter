# --- Core Django config ---

from pathlib import Path
import os

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    raise RuntimeError(f"{name} must be set")


SECRET_KEY = _require_env("DJANGO_SECRET_KEY")

DEBUG = os.getenv("DJANGO_DEBUG", "0") == "1"

def _split_csv(v: str) -> list[str]:
    return [x.strip() for x in v.split(",") if x.strip()]


ALLOWED_HOSTS = _split_csv(os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1"))
OPENAPI_PUBLIC_ENABLED = os.getenv("OPENAPI_PUBLIC_ENABLED", "0") == "1"


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Step 11
    "corsheaders",
    "drf_spectacular",

    "rest_framework",
    "apps.authn",
    "apps.nsi_core",
    "apps.catalog",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.authn.authentication.KeycloakJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    # Step 11: OpenAPI schema generation
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

MIDDLEWARE = [
    # Step 11: must be before CommonMiddleware
    "corsheaders.middleware.CorsMiddleware",

    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "nsi_service.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "nsi_service.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(default=os.environ["DATABASE_URL"], conn_max_age=60)
}

# --- Locale ---
LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Amsterdam"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Step 11: CORS for frontend dev
CORS_ALLOWED_ORIGINS = _split_csv(
    os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")
)

# Step 11: Swagger/OpenAPI settings
SPECTACULAR_SETTINGS = {
    "TITLE": "NSI API",
    "DESCRIPTION": "Converter prototype – NSI service",
    "VERSION": "0.1.0",
    "SECURITY": [{"bearerAuth": []}],
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api",
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
    },
}
