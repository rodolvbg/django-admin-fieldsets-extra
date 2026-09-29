import importlib.util
import os
import tempfile
from pathlib import Path

SECRET_KEY = "test-secret-key"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_admin_fieldsets_with_inlines",
    "demo",
]
# Integration tests run when django-admin-inline-controls is installed.
if importlib.util.find_spec("django_admin_inline_controls"):
    INSTALLED_APPS.append("django_admin_inline_controls")

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "tests.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Files, not ":memory:": pytest-django's live_server shares one connection
# across its threads when the database looks in-memory, and concurrent
# browser requests in the e2e tests would then use it at once.
_DB_BASE = (
    Path(tempfile.gettempdir()) / f"django-admin-fieldsets-with-inlines-{os.getpid()}"
)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": f"{_DB_BASE}.sqlite3",
        "TEST": {"NAME": f"{_DB_BASE}-test.sqlite3"},
    }
}

STATIC_URL = "static/"

USE_TZ = True
