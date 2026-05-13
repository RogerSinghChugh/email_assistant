"""Reporting endpoints — admin (firm-scoped) and superuser (global)."""

from datetime import datetime

from django.utils.dateparse import parse_datetime
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from apps.core.permissions import IsFirmAdmin, IsSuperuser
from apps.reports.repositories import ReportRepository
from apps.reports.serializers import (
    FirmClientReportRowSerializer,
    GlobalFirmReportRowSerializer,
)


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    # Accept date or datetime ISO strings.
    parsed = parse_datetime(value)
    if parsed is not None:
        return parsed
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class FirmReportView(ListAPIView):
    """GET /api/reports/firm/?since=&until= — admin only, firm-scoped."""

    serializer_class = FirmClientReportRowSerializer
    permission_classes = (IsAuthenticated, IsFirmAdmin)

    def get_queryset(self):
        return ReportRepository.firm_clients_with_summaries(
            firm_id=self.request.user.firm_id,
            since=_parse_date(self.request.query_params.get("since")),
            until=_parse_date(self.request.query_params.get("until")),
        )


class GlobalReportView(ListAPIView):
    """GET /api/reports/global/?since=&until= — superuser only."""

    serializer_class = GlobalFirmReportRowSerializer
    permission_classes = (IsAuthenticated, IsSuperuser)

    def get_queryset(self):
        return ReportRepository.global_grouped_by_firm(
            since=_parse_date(self.request.query_params.get("since")),
            until=_parse_date(self.request.query_params.get("until")),
        )
