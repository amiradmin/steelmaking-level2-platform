from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "level2-dev-only-secret-key")
DEBUG = os.getenv("DJANGO_DEBUG", "0").lower() in {"1", "true", "yes", "on"}
ALLOWED_HOSTS = [
    value.strip()
    for value in os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")
    if value.strip()
]

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "level2_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "level2_project.wsgi.application"
ASGI_APPLICATION = "level2_project.asgi.application"
TELEMETRY_PUSH_INTERVAL_SECONDS = float(
    os.getenv("TELEMETRY_PUSH_INTERVAL_SECONDS", "1.0")
)
TELEMETRY_STALE_AFTER_SECONDS = float(
    os.getenv("TELEMETRY_STALE_AFTER_SECONDS", "5.0")
)

if os.getenv("DJANGO_TEST_SQLITE", "0").lower() in {"1", "true", "yes", "on"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "test.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "steelmaking_level2"),
            "USER": os.getenv("POSTGRES_USER", "level2"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", "level2_dev_password"),
            "HOST": os.getenv("DB_HOST", "historian-db"),
            "PORT": os.getenv("DB_PORT", "5432"),
            "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
        }
    }

AUTH_PASSWORD_VALIDATORS: list[dict[str, str]] = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=int(os.getenv("JWT_ACCESS_MINUTES", "15"))
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        hours=int(os.getenv("JWT_REFRESH_HOURS", "12"))
    ),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Steelmaking Level 2 API",
    "DESCRIPTION": (
        "Versioned public API for Level 2 dashboard and integration consumers. "
        "Domain write operations remain in dedicated FastAPI services."
    ),
    "VERSION": "0.2.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

_cors_origins = [
    value.strip()
    for value in os.getenv("API_CORS_ORIGINS", "*").split(",")
    if value.strip()
]
CORS_ALLOW_ALL_ORIGINS = "*" in _cors_origins
CORS_ALLOWED_ORIGINS = [value for value in _cors_origins if value != "*"]
CORS_ALLOW_CREDENTIALS = False
