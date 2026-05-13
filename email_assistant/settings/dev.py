"""Development settings — relaxed defaults, dev SALT_KEY fallback."""

import logging

from .base import *  # noqa: F401,F403
from .base import SALT_KEY

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Dev-only fallback salt so first-run "just works". DO NOT use in prod.
if not SALT_KEY:
    SALT_KEY = ["dev-only-salt-do-not-use-in-prod"]
    logging.getLogger(__name__).warning(
        "SALT_KEYS env var not set — falling back to dev salt. "
        "Set SALT_KEYS in .env for any non-dev use."
    )
