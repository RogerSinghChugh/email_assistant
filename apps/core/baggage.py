"""OpenTelemetry baggage helpers — cross-process request-context propagation.

OTel baggage is the standard way to carry small key/value pairs alongside the
trace context. CeleryInstrumentor (and other auto-instrumentations) serialize
baggage into task headers / outbound HTTP headers, so values set in the web
process automatically become visible in the worker process.

We use it for ``request_id``, ``user_id``, and ``firm_id`` so log lines in the
Celery worker can be filtered by the same fields as web-side logs.

Usage:

    with request_baggage(request):
        refresh_summary_task.apply_async(...)
        # any code inside this block has the baggage set on the OTel context

Outside the with-block, the previous context is restored.

When OTel isn't installed/initialised the helpers are no-ops; the ``with``
block still works, and the worker side simply falls back to "-" in logs.
"""

from __future__ import annotations

import contextlib
from typing import Iterator


@contextlib.contextmanager
def request_baggage(request) -> Iterator[None]:
    """Attach request_id / user_id / firm_id to the current OTel context for the duration of the block."""
    try:
        from opentelemetry import baggage, context
    except ImportError:
        yield
        return

    ctx = context.get_current()
    req_id = getattr(request, "id", None)
    if req_id:
        ctx = baggage.set_baggage("request_id", str(req_id), context=ctx)

    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        ctx = baggage.set_baggage("user_id", str(user.pk), context=ctx)
        firm_id = getattr(user, "firm_id", None)
        if firm_id is not None:
            ctx = baggage.set_baggage("firm_id", str(firm_id), context=ctx)

    token = context.attach(ctx)
    try:
        yield
    finally:
        context.detach(token)
