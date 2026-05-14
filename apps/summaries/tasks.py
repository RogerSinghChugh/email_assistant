"""Celery tasks for summary refresh."""

from __future__ import annotations

import logging

from celery import shared_task

from apps.summaries.services.cache import (
    acquire_lock,
    invalidate_firm_reports,
    invalidate_summary,
    release_inflight,
    release_lock,
)
from apps.summaries.services.summarizer import SummaryService

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="summaries.refresh_summary")
def refresh_summary_task(self, thread_id: str) -> dict:
    """Idempotent refresh task.

    Acquires a Redis SETNX lock so concurrent triggers don't fan out to N LLM calls.
    Invalidates the summary cache + per-firm report cache on success.
    """
    if not acquire_lock(thread_id):
        logger.info(
            "summary.refresh.skipped_locked",
            extra={"action": "summary.refresh.skipped_locked", "duration_ms": "-"},
        )
        return {"status": "skipped", "reason": "another_refresh_in_progress"}

    try:
        result = SummaryService().refresh(thread_id)
        invalidate_summary(thread_id)
        invalidate_firm_reports(result.summary.firm_id)
        return {
            "status": "ok",
            "thread_id": str(result.summary.thread_id),
            "emails_analyzed": result.emails_analyzed,
            "last_refreshed_at": result.summary.last_refreshed_at.isoformat(),
        }
    finally:
        release_lock(thread_id)
        release_inflight(thread_id)
