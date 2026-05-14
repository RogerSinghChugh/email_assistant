"""Report data access — aggregations across summaries / threads / clients."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from django.db.models import QuerySet

from apps.summaries.models import EmailSummary


def _apply_date_filter(
    qs: QuerySet, *, since: datetime | None, until: datetime | None
) -> QuerySet:
    if since is not None:
        qs = qs.filter(last_refreshed_at__gte=since)
    if until is not None:
        qs = qs.filter(last_refreshed_at__lte=until)
    return qs


def _summary_entry(s: EmailSummary, *, include_client: bool = False) -> dict[str, Any]:
    entry = {
        "id": s.id,
        "thread_id": s.thread_id,
        # ``encrypted_subject`` is transparently decrypted by ``from_db_value``.
        "thread_subject": s.thread.encrypted_subject or "(no subject)",
        "emails_analyzed": s.emails_analyzed,
        "last_refreshed_at": s.last_refreshed_at,
        "up_to_message_at": s.up_to_message_at,
    }
    if include_client:
        entry["client_id"] = s.thread.client_id
        entry["client_name"] = s.thread.client.name
    return entry


class ReportRepository:
    @staticmethod
    def firm_clients_with_summaries(
        firm_id,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Drillable per-client rows for one firm.

        Each row carries both aggregate counts AND the underlying summary list
        so the UI can show "Heather Martin · 3 summaries" and expand to the
        individual thread subjects without a follow-up request.
        """
        qs = (
            EmailSummary.objects.filter(firm_id=firm_id)
            .select_related("thread", "thread__client")
            .order_by("-last_refreshed_at")
        )
        qs = _apply_date_filter(qs, since=since, until=until)

        groups: dict[Any, list[EmailSummary]] = defaultdict(list)
        for s in qs:
            groups[s.thread.client_id].append(s)

        rows: list[dict[str, Any]] = []
        for summaries in groups.values():
            client = summaries[0].thread.client
            rows.append(
                {
                    "client_id": client.id,
                    "client_name": client.name,
                    "client_email": client.email,
                    "summary_count": len(summaries),
                    "total_emails_analyzed": sum(s.emails_analyzed for s in summaries),
                    "last_summarized": max(s.last_refreshed_at for s in summaries),
                    "summaries": [_summary_entry(s) for s in summaries],
                }
            )
        rows.sort(key=lambda r: r["last_summarized"], reverse=True)
        return rows

    @staticmethod
    def global_grouped_by_firm(
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Per-firm aggregate rows + drillable summary list for superusers."""
        qs = (
            EmailSummary.objects.all()
            .select_related("firm", "thread", "thread__client")
            .order_by("-last_refreshed_at")
        )
        qs = _apply_date_filter(qs, since=since, until=until)

        groups: dict[Any, list[EmailSummary]] = defaultdict(list)
        for s in qs:
            groups[s.firm_id].append(s)

        rows: list[dict[str, Any]] = []
        for summaries in groups.values():
            firm = summaries[0].firm
            distinct_clients = {s.thread.client_id for s in summaries}
            rows.append(
                {
                    "firm_id": firm.id,
                    "firm_name": firm.name,
                    "summary_count": len(summaries),
                    "client_count": len(distinct_clients),
                    "total_emails_analyzed": sum(s.emails_analyzed for s in summaries),
                    "last_summarized": max(s.last_refreshed_at for s in summaries),
                    "summaries": [
                        _summary_entry(s, include_client=True) for s in summaries
                    ],
                }
            )
        rows.sort(key=lambda r: r["summary_count"], reverse=True)
        return rows
