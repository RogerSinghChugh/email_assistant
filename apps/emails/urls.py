"""Email-thread URL routes."""

from django.urls import path

from apps.emails.views import (
    ClientThreadListView,
    SampleThreadListView,
    ThreadDetailView,
)

urlpatterns = [
    path(
        "clients/<uuid:client_id>/threads/",
        ClientThreadListView.as_view(),
        name="client-thread-list",
    ),
    path("threads/sample/", SampleThreadListView.as_view(), name="thread-sample"),
    path("threads/<uuid:pk>/", ThreadDetailView.as_view(), name="thread-detail"),
]
