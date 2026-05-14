"""Base settings shared by all environments. Env-driven via django-environ."""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
env.read_env(BASE_DIR / ".env")

# --- Core ---------------------------------------------------------------
SECRET_KEY = env(
    "DJANGO_SECRET_KEY", default="django-insecure-dev-only-do-not-use-in-prod"
)
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# --- Apps ---------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]
THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
]
LOCAL_APPS = [
    "apps.accounts",
    "apps.core",
    "apps.clients",
    "apps.emails",
    "apps.summaries",
    "apps.reports",
]
INSTALLED_APPS = DJANGO_APPS + LOCAL_APPS + THIRD_PARTY_APPS

# --- Middleware ---------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "apps.core.middleware.RequestIdMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "email_assistant.urls"
WSGI_APPLICATION = "email_assistant.wsgi.application"

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
            ],
        },
    },
]

# --- Database -----------------------------------------------------------
DATABASES = {
    "default": env.db_url(
        "DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
    ),
}

AUTH_USER_MODEL = "accounts.Accountant"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Redis / Cache ------------------------------------------------------
REDIS_URL = env("REDIS_URL", default="redis://127.0.0.1:6379/1")
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "email_assistant",
        "TIMEOUT": 300,
    }
}

# --- Celery -------------------------------------------------------------
CELERY_BROKER_URL = env(
    "CELERY_BROKER_URL", default=env("REDIS_URL", default="redis://127.0.0.1:6379/0")
)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_RESULT_EXPIRES = 3600
CELERY_TIMEZONE = "UTC"
CELERY_WORKER_HIJACK_ROOT_LOGGER = False
# Dedicated queue so this app's tasks aren't consumed by other Celery apps
# sharing the same Redis broker on this machine.
CELERY_TASK_DEFAULT_QUEUE = "email_assistant"

# --- DRF ----------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.DefaultPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "apps.core.exceptions.exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": ("rest_framework.throttling.ScopedRateThrottle",),
    "DEFAULT_THROTTLE_RATES": {
        "summary_refresh": "10/min",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "TOKEN_OBTAIN_SERIALIZER": "apps.accounts.serializers.CustomTokenObtainPairSerializer",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Email Context API",
    "DESCRIPTION": "Email summarization service for CPA firms.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# --- Encryption ---------------------------------------------------------
# django-fernet-encrypted-fields derives a Fernet key via PBKDF2-HMAC-SHA256
# from SECRET_KEY salted with SALT_KEY. Rotate by appending old salts to the list
# (or use SECRET_KEY_FALLBACKS) — MultiFernet tries each combination on read.
SALT_KEY = env.list("SALT_KEYS", default=[])

# --- LLM / OpenRouter ---------------------------------------------------
OPENROUTER_API_KEY = env("OPENROUTER_API_KEY", default="")
LLM_BASE_URL = env("LLM_BASE_URL", default="https://openrouter.ai/api/v1")
LLM_MODEL = env("LLM_MODEL", default="google/gemini-2.0-flash-001")
LLM_TIMEOUT_SEC = env.int("LLM_TIMEOUT_SEC", default=30)
LLM_MAX_RETRIES = env.int("LLM_MAX_RETRIES", default=3)

# --- Logging ------------------------------------------------------------
LOG_LEVEL = env("LOG_LEVEL", default="INFO")
LOG_DIR = Path(env("LOG_DIR", default=str(BASE_DIR / "logs")))
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"

_LOG_FORMAT = (
    "%(asctime)s %(levelname)s %(name)s %(message)s "
    "%(request_id)s %(user_id)s %(firm_id)s %(action)s %(duration_ms)s"
)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "context": {"()": "apps.core.logging.ContextFilter"},
    },
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "format": _LOG_FORMAT,
        },
        "console": {
            "format": "[%(asctime)s] %(levelname)s %(name)s [req=%(request_id)s user=%(user_id)s firm=%(firm_id)s] %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console",
            "filters": ["context"],
        },
        "logfile": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_FILE),
            "maxBytes": 10_485_760,
            "backupCount": 5,
            "formatter": "json",
            "filters": ["context"],
            "encoding": "utf-8",
        },
    },
    "loggers": {
        "": {"handlers": ["console", "logfile"], "level": LOG_LEVEL},
        "django": {
            "handlers": ["console", "logfile"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", "logfile"],
            "level": "WARNING",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console", "logfile"],
            "level": "INFO",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console", "logfile"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "openai": {
            "handlers": ["console", "logfile"],
            "level": "WARNING",
            "propagate": False,
        },
        "httpx": {
            "handlers": ["console", "logfile"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
