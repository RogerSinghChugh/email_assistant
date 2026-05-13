"""Clients URL routes."""

from django.urls import path

from apps.clients.views import ClientDetailView, ClientListView

urlpatterns = [
    path("clients/", ClientListView.as_view(), name="client-list"),
    path("clients/<uuid:pk>/", ClientDetailView.as_view(), name="client-detail"),
]
