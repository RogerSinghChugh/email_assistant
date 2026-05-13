"""Test settings — eager Celery, in-memory cache, hardcoded salt."""

from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = ["*"]

# Hardcoded test salt — deterministic across machines.
SALT_KEY = ["test-salt-deterministic"]

# Run Celery tasks synchronously in the test process.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# In-memory cache so tests don't need Redis.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-cache",
    }
}

# Speed up password hashing in tests.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
