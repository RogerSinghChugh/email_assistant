"""Reports URL routes."""

from django.urls import path

from apps.reports.views import FirmReportView, GlobalReportView

urlpatterns = [
    path("firm/", FirmReportView.as_view(), name="report-firm"),
    path("global/", GlobalReportView.as_view(), name="report-global"),
]
