"""OpenTelemetry setup — OTLP export of traces + logs to any OTLP backend (Grafana Cloud, Signoz, Honeycomb, Jaeger, etc.).

Gated by ``OTEL_ENABLED`` — when off, this module is a no-op and the OTel
packages need not even be installed. When on, it:

1. Configures the global ``TracerProvider`` with a batch OTLP/HTTP exporter.
2. Configures the global ``LoggerProvider`` and attaches a ``LoggingHandler``
   to the root logger so every existing ``logger.info(...)`` call ships to
   the backend with the active ``trace_id`` + ``span_id`` already baked in.
3. Auto-instruments Django, Celery, Redis, and httpx (which the OpenAI SDK
   uses for OpenRouter calls) so a single trace spans
   ``view → cache → enqueue → worker → LLM → DB write``.

Configuration uses standard OTel env vars (read by the exporters at init):

    OTEL_ENABLED=true
    OTEL_SERVICE_NAME=email_assistant
    OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-prod-us-east-0.grafana.net/otlp
    OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
    OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic <base64(instance_id:api_token)>
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_initialised = False


def is_enabled() -> bool:
    return os.environ.get("OTEL_ENABLED", "").lower() in ("1", "true", "yes")


def setup_telemetry() -> None:
    """Idempotent. Safe to call from Django ``ready()`` and Celery init."""
    global _initialised
    if _initialised or not is_enabled():
        return

    try:
        from opentelemetry import trace
        from opentelemetry._logs import set_logger_provider
        from opentelemetry.exporter.otlp.proto.http._log_exporter import (
            OTLPLogExporter,
        )
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.celery import CeleryInstrumentor
        from opentelemetry.instrumentation.django import DjangoInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        from opentelemetry.instrumentation.sqlite3 import SQLite3Instrumentor
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        logger.warning("OTel disabled — packages missing: %s", exc)
        return

    resource = Resource.create(
        {
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "email_assistant"),
            "service.namespace": "assistant",
        }
    )

    # --- Traces -----------------------------------------------------------
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    # --- Logs -------------------------------------------------------------
    log_provider = LoggerProvider(resource=resource)
    log_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    set_logger_provider(log_provider)
    log_level = logging._nameToLevel.get(
        os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO
    )
    handler = LoggingHandler(level=log_level, logger_provider=log_provider)
    # Our LOGGING dict sets propagate=False on every named logger to avoid
    # double-emit to console+logfile. That also stops records from reaching the
    # root logger — so attaching only to root would silently drop everything.
    # Attach the OTel handler directly to each top-level logger we care about.
    for name in ("", "django", "celery", "apps"):
        logging.getLogger(name).addHandler(handler)

    # --- Auto-instrument the libraries we use ----------------------------
    DjangoInstrumentor().instrument()
    CeleryInstrumentor().instrument()
    RedisInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()  # OpenAI SDK uses httpx
    SQLite3Instrumentor().instrument()  # DB query spans (swap for psycopg2 in prod)

    _initialised = True
    logger.info(
        "opentelemetry initialised",
        extra={"action": "otel.init", "duration_ms": "-"},
    )


def current_trace_id() -> str:
    """Hex trace_id of the active span, or "-" if none."""
    try:
        from opentelemetry import trace

        ctx = trace.get_current_span().get_span_context()
        if ctx.is_valid:
            return format(ctx.trace_id, "032x")
    except ImportError:
        pass
    return "-"


def current_span_id() -> str:
    """Hex span_id of the active span, or "-" if none."""
    try:
        from opentelemetry import trace

        ctx = trace.get_current_span().get_span_context()
        if ctx.is_valid:
            return format(ctx.span_id, "016x")
    except ImportError:
        pass
    return "-"
