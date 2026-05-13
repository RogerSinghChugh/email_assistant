"""Summary endpoints — strict 404 on miss + async refresh via Celery."""

from __future__ import annotations

import logging

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

from apps.core.permissions import IsInSameFirm  # noqa: F401  (imported for future per-object checks)
from apps.emails.models import EmailThread
from apps.summaries.repositories import SummaryRepository
from apps.summaries.serializers import SummaryReadSerializer, TaskStatusSerializer
from apps.summaries.services.cache import SUMMARY_TTL_SECONDS, summary_key
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

        async_result = refresh_summary_task.apply_async(
            args=[str(thread_id)],
            headers={"request_id": getattr(request, "id", None)},
        )
        return Response(
            {
                "task_id": async_result.id,
                "status_url": reverse(
                    "task-status", kwargs={"task_id": async_result.id}
                ),
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
