"""Core URLs."""

from django.urls import path

from apps.core.views import HealthcheckView

urlpatterns = [
    path("", HealthcheckView.as_view(), name="health"),
]
