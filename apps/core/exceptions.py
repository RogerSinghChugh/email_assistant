"""DRF exception handler — returns {detail, code, request_id}."""

from rest_framework.views import exception_handler as drf_exception_handler

from apps.core.logging import request_id_var


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    request_id = request_id_var.get() or "-"
    if isinstance(response.data, dict):
        response.data.setdefault("request_id", request_id)
        response.data.setdefault("code", getattr(exc, "default_code", "error"))
    return response
