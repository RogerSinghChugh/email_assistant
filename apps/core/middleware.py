"""Request-ID middleware — sets contextvars and echoes X-Request-ID response header."""

import time
import uuid
import logging

from apps.core.logging import firm_id_var, request_id_var, user_id_var

logger = logging.getLogger("apps.core.requests")


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        req_id = request.META.get("HTTP_X_REQUEST_ID") or uuid.uuid4().hex
        request.id = req_id

        rid_token = request_id_var.set(req_id)
        uid_token = None
        fid_token = None

        start = time.perf_counter()
        try:
            response = self.get_response(request)
            # User is only populated after auth middleware runs (i.e., during the view).
            user = getattr(request, "user", None)
            if user is not None and getattr(user, "is_authenticated", False):
                uid_token = user_id_var.set(str(user.pk))
                firm_id = getattr(user, "firm_id", None)
                if firm_id is not None:
                    fid_token = firm_id_var.set(str(firm_id))
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.info(
                "%s %s -> %s",
                request.method,
                request.path,
                response.status_code,
                extra={"action": "http.request", "duration_ms": duration_ms},
            )
        finally:
            request_id_var.reset(rid_token)
            if uid_token is not None:
                user_id_var.reset(uid_token)
            if fid_token is not None:
                firm_id_var.reset(fid_token)
        response["X-Request-ID"] = req_id
        return response
