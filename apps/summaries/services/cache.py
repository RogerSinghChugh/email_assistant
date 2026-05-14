"""Cache key constants + helpers. Keeps cache concerns in one place."""

from __future__ import annotations

from django.core.cache import cache

SUMMARY_TTL_SECONDS = 60 * 60  # 1 hour
LOCK_TTL_SECONDS = 120  # 2 minutes — comfortably more than an LLM call
INFLIGHT_TTL_SECONDS = 120  # mirrors LOCK_TTL — auto-clears if a worker dies mid-task


def summary_key(thread_id) -> str:
    return f"summary:{thread_id}"


def lock_key(thread_id) -> str:
    return f"summary_lock:{thread_id}"


def inflight_key(thread_id) -> str:
    return f"summary_inflight:{thread_id}"


def acquire_lock(thread_id) -> bool:
    """SETNX-style lock; returns True if we got the lock, False if someone else holds it."""
    return bool(cache.add(lock_key(thread_id), "1", timeout=LOCK_TTL_SECONDS))


def release_lock(thread_id) -> None:
    cache.delete(lock_key(thread_id))


def try_claim_inflight(thread_id, task_id: str) -> bool:
    """Atomically reserve the inflight slot for ``thread_id`` and store our ``task_id``.

    Returns True if we claimed the slot (caller should enqueue the task);
    False if a previous refresh is still in flight (caller should join it).
    """
    return bool(
        cache.add(inflight_key(thread_id), task_id, timeout=INFLIGHT_TTL_SECONDS)
    )


def get_inflight(thread_id) -> str | None:
    """Return the task_id of the currently in-flight refresh for this thread, if any."""
    return cache.get(inflight_key(thread_id))


def release_inflight(thread_id) -> None:
    cache.delete(inflight_key(thread_id))


def invalidate_summary(thread_id) -> None:
    cache.delete(summary_key(thread_id))


def invalidate_firm_reports(firm_id) -> None:
    """Best-effort: delete all per-firm report keys.

    django-redis exposes ``cache.delete_pattern`` for this. Wrapped in a try
    so the call is safe under in-memory cache backends used in tests.
    """
    try:
        cache.delete_pattern(f"report:firm:{firm_id}:*")
    except (AttributeError, NotImplementedError):
        pass
