"""Summary endpoints — strict 404 on miss + async refresh via Celery."""

from __future__ import annotations

import logging
import uuid

from celery.result import AsyncResult
from django.core.cache import cache
from django.urls import reverse
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.baggage import request_baggage
from apps.core.permissions import IsInSameFirm  # noqa: F401  (imported for future per-object checks)
from apps.emails.models import EmailThread
from apps.summaries.repositories import SummaryRepository
from apps.summaries.serializers import SummaryReadSerializer, TaskStatusSerializer
from apps.summaries.services.cache import (
    SUMMARY_TTL_SECONDS,
    get_inflight,
    summary_key,
    try_claim_inflight,
)
from apps.summaries.tasks import refresh_summary_task

logger = logging.getLogger(__name__)


def _is_superuser(user) -> bool:
    return bool(getattr(user, "is_role_superuser", False))


def _check_thread_access(request, thread_id):
    """Resolve the thread firm-scoped — raises ``EmailThread.DoesNotExist`` for cross-firm/non-existent."""
    if _is_superuser(request.user):
        return EmailThread.objects.get(pk=thread_id)
    return EmailThread.objects.get(pk=thread_id, firm_id=request.user.firm_id)


class SummaryRetrieveView(RetrieveAPIView):
    """GET /api/threads/{thread_id}/summary/.

    Strict 404 with ``refresh_url`` on miss — generation is explicit via POST refresh.
    """

    serializer_class = SummaryReadSerializer
    permission_classes = (IsAuthenticated,)

    def get(self, request, thread_id):
        try:
            _check_thread_access(request, thread_id)
        except EmailThread.DoesNotExist:
            return Response(
                {"detail": "Thread not found."}, status=status.HTTP_404_NOT_FOUND
            )

        cache_k = summary_key(thread_id)
        cached = cache.get(cache_k)
        if cached is not None:
            logger.debug(
                "summary.cache.hit",
                extra={"action": "summary.cache.hit", "duration_ms": "-"},
            )
            return Response(cached)

        summary = SummaryRepository.get_or_none(thread_id)
        if summary is None:
            return Response(
                {
                    "detail": "not_generated",
                    "refresh_url": reverse(
                        "summary-refresh", kwargs={"thread_id": thread_id}
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        data = SummaryReadSerializer(summary).data
        cache.set(cache_k, data, timeout=SUMMARY_TTL_SECONDS)
        logger.debug(
            "summary.cache.miss",
            extra={"action": "summary.cache.miss", "duration_ms": "-"},
        )
        return Response(data)


class SummaryRefreshView(APIView):
    """POST /api/threads/{thread_id}/summary/refresh/."""

    permission_classes = (IsAuthenticated,)
    throttle_scope = "summary_refresh"

    @extend_schema(
        request=None,
        responses={
            202: inline_serializer(
                name="RefreshAccepted",
                fields={
                    "task_id": drf_serializers.CharField(),
                    "status_url": drf_serializers.CharField(),
                    "joined": drf_serializers.BooleanField(),
                },
            ),
            404: OpenApiResponse(description="Thread not found in your firm."),
        },
    )
    def post(self, request, thread_id):
        try:
            _check_thread_access(request, thread_id)
        except EmailThread.DoesNotExist:
            return Response(
                {"detail": "Thread not found."}, status=status.HTTP_404_NOT_FOUND
            )

        # Fan-in: if a refresh for this thread is already in flight, return its
        # task_id so concurrent triggers all converge on the same poll instead
        # of producing N parallel tasks (the worker's lock would skip them, but
        # the user-facing UX is cleaner if we collapse at the API edge).
        #
        # ``request_baggage`` puts request_id/user_id/firm_id into the OTel
        # context — CeleryInstrumentor serializes baggage into task headers, so
        # the worker's log lines inherit the same identifiers.
        new_task_id = str(uuid.uuid4())
        with request_baggage(request):
            claimed = try_claim_inflight(str(thread_id), new_task_id)
            if claimed:
                refresh_summary_task.apply_async(
                    args=[str(thread_id)], task_id=new_task_id
                )
                task_id, joined = new_task_id, False
            else:
                existing = get_inflight(str(thread_id))
                if existing:
                    task_id, joined = existing, True
                else:
                    refresh_summary_task.apply_async(
                        args=[str(thread_id)], task_id=new_task_id
                    )
                    task_id, joined = new_task_id, False

        return Response(
            {
                "task_id": task_id,
                "status_url": reverse("task-status", kwargs={"task_id": task_id}),
                "joined": joined,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class TaskStatusView(APIView):
    """GET /api/tasks/{task_id}/."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=TaskStatusSerializer)
    def get(self, request, task_id):
        result = AsyncResult(task_id)
        payload = {
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.successful() else None,
        }
        if result.failed():
            payload["error"] = str(result.result)
        return Response(TaskStatusSerializer(payload).data)
