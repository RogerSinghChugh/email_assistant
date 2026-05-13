"""Summary URL routes."""

from django.urls import path

from apps.summaries.views import SummaryRefreshView, SummaryRetrieveView, TaskStatusView

urlpatterns = [
    path(
        "threads/<uuid:thread_id>/summary/",
        SummaryRetrieveView.as_view(),
        name="summary-detail",
    ),
    path(
        "threads/<uuid:thread_id>/summary/refresh/",
        SummaryRefreshView.as_view(),
        name="summary-refresh",
    ),
    path("tasks/<str:task_id>/", TaskStatusView.as_view(), name="task-status"),
]
