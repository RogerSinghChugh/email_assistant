"""Production settings — strict, fail-fast on missing config."""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import OPENROUTER_API_KEY, SALT_KEY

DEBUG = False

if not SALT_KEY:
    raise ImproperlyConfigured("SALT_KEYS env var is required in production.")
if not OPENROUTER_API_KEY:
    raise ImproperlyConfigured("OPENROUTER_API_KEY env var is required in production.")
