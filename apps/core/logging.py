"""Structured logging — context propagation via contextvars + JSON logfile.

Provides:
- ``ContextFilter`` — injects request_id / user_id / firm_id / action / duration_ms
  into every ``LogRecord`` from contextvars.
- ``@log_action(name)`` decorator — emits a single INFO log on success with timing,
  and ``logger.exception(...)`` on failure.
- ``ensure_log_dir()`` — creates LOG_DIR at app boot (called from CoreConfig.ready).
- ``register_celery_signal_handlers()`` — propagates request_id from task headers
  into worker logs.
"""

from __future__ import annotations

import functools
import logging
import time
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Callable

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)
firm_id_var: ContextVar[str | None] = ContextVar("firm_id", default=None)


class ContextFilter(logging.Filter):
    """Pull contextvars + active OTel span ids onto every record.

    Adds:
      - request_id / user_id / firm_id (contextvars set by middleware/Celery signals)
      - trace_id / span_id (from the active OpenTelemetry span; "-" when OTel off)
      - action / duration_ms (defaulted; populated by @log_action decorator)
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        record.user_id = user_id_var.get() or "-"
        record.firm_id = firm_id_var.get() or "-"
        if not hasattr(record, "action"):
            record.action = "-"
        if not hasattr(record, "duration_ms"):
            record.duration_ms = "-"

        # Cross-process fallback: OTel baggage propagates these from the web
        # process to the Celery worker via task headers. In the worker the local
        # contextvars are empty; baggage carries the values forward.
        if "-" in (record.request_id, record.user_id, record.firm_id):
            try:
                from opentelemetry import baggage

                if record.request_id == "-":
                    record.request_id = baggage.get_baggage("request_id") or "-"
                if record.user_id == "-":
                    record.user_id = baggage.get_baggage("user_id") or "-"
                if record.firm_id == "-":
                    record.firm_id = baggage.get_baggage("firm_id") or "-"
            except ImportError:
                pass

        from apps.core.telemetry import current_span_id, current_trace_id

        record.trace_id = current_trace_id()
        record.span_id = current_span_id()
        return True


def ensure_log_dir() -> None:
    """Idempotent log-directory creation. Called from CoreConfig.ready()."""
    from django.conf import settings

    log_dir = Path(getattr(settings, "LOG_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)


def log_action(action: str, logger_name: str | None = None) -> Callable:
    """Decorator: emit a single INFO log on success with duration_ms; logger.exception on failure."""

    def decorator(func: Callable) -> Callable:
        log = logging.getLogger(logger_name or func.__module__)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
            except Exception:
                duration_ms = int((time.perf_counter() - start) * 1000)
                log.exception(
                    "%s failed",
                    action,
                    extra={"action": action, "duration_ms": duration_ms},
                )
                raise
            duration_ms = int((time.perf_counter() - start) * 1000)
            log.info(
                "%s ok", action, extra={"action": action, "duration_ms": duration_ms}
            )
            return result

        return wrapper

    return decorator


def register_celery_signal_handlers() -> None:
    """Wire request_id propagation into Celery worker logs.

    Tasks enqueued with ``apply_async(headers={"request_id": ...})`` (or via our
    helper) carry the request_id into the worker context.
    """
    try:
        from celery.signals import task_postrun, task_prerun
    except ImportError:  # Celery not installed yet — bail silently.
        return

    _token_stash: dict[str, list] = {}

    @task_prerun.connect
    def _on_prerun(task_id: str, task, **kwargs):  # noqa: ARG001
        req_id = (
            (getattr(task.request, "headers", None) or {}).get("request_id")
            if task and getattr(task, "request", None)
            else None
        )
        tokens = []
        tokens.append(request_id_var.set(req_id or task_id))
        _token_stash[task_id] = tokens

    @task_postrun.connect
    def _on_postrun(task_id: str, **kwargs):  # noqa: ARG001
        tokens = _token_stash.pop(task_id, [])
        for tok in reversed(tokens):
            try:
                request_id_var.reset(tok)
            except ValueError:
                pass
