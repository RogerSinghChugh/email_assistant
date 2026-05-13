"""Report data access — aggregations across summaries / threads / clients."""

from __future__ import annotations

from datetime import datetime

from django.db.models import Count, Max, QuerySet, Sum

from apps.summaries.models import EmailSummary


def _apply_date_filter(
    qs: QuerySet, *, since: datetime | None, until: datetime | None
) -> QuerySet:
    if since is not None:
        qs = qs.filter(last_refreshed_at__gte=since)
    if until is not None:
        qs = qs.filter(last_refreshed_at__lte=until)
    return qs


class ReportRepository:
    @staticmethod
    def firm_clients_with_summaries(
        firm_id,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> QuerySet:
        """Drillable per-client rows for one firm.

        One row per client that has at least one summary in the date window,
        with aggregated counts and timestamps.
        """
        qs = EmailSummary.objects.filter(firm_id=firm_id)
        qs = _apply_date_filter(qs, since=since, until=until)
        return (
            qs.values(
                "thread__client_id",
                "thread__client__name",
                "thread__client__email",
            )
            .annotate(
                summary_count=Count("id"),
                total_emails_analyzed=Sum("emails_analyzed"),
                last_summarized=Max("last_refreshed_at"),
            )
            .order_by("-last_summarized")
        )

    @staticmethod
    def global_grouped_by_firm(
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> QuerySet:
        """Per-firm aggregate rows for superusers."""
        qs = EmailSummary.objects.all()
        qs = _apply_date_filter(qs, since=since, until=until)
        return (
            qs.values("firm_id", "firm__name")
            .annotate(
                summary_count=Count("id"),
                client_count=Count("thread__client_id", distinct=True),
                total_emails_analyzed=Sum("emails_analyzed"),
                last_summarized=Max("last_refreshed_at"),
            )
            .order_by("-summary_count")
        )
