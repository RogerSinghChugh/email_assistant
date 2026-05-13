"""Cache key constants + helpers. Keeps cache concerns in one place."""

from __future__ import annotations

from django.core.cache import cache

SUMMARY_TTL_SECONDS = 60 * 60  # 1 hour
LOCK_TTL_SECONDS = 120  # 2 minutes — comfortably more than an LLM call


def summary_key(thread_id) -> str:
    return f"summary:{thread_id}"


def lock_key(thread_id) -> str:
    return f"summary_lock:{thread_id}"


def acquire_lock(thread_id) -> bool:
    """SETNX-style lock; returns True if we got the lock, False if someone else holds it."""
    return bool(cache.add(lock_key(thread_id), "1", timeout=LOCK_TTL_SECONDS))


def release_lock(thread_id) -> None:
    cache.delete(lock_key(thread_id))


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
