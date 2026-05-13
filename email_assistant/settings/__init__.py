"""Settings package — dispatches to dev/prod/test based on DJANGO_ENV or sys.argv."""

import os
import sys

_env = os.environ.get("DJANGO_ENV")
if _env is None:
    _env = "test" if "test" in sys.argv else "dev"

if _env == "prod":
    from .prod import *  # noqa: F401,F403
elif _env == "test":
    from .test import *  # noqa: F401,F403
else:
    from .dev import *  # noqa: F401,F403
