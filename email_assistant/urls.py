"""Root URL configuration for email_assistant.

App-level URL includes are uncommented as each app's `urls.py` lands.
"""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", include("apps.core.urls")),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/", include("apps.clients.urls")),
    path("api/", include("apps.emails.urls")),
    path("api/", include("apps.summaries.urls")),
    path("api/reports/", include("apps.reports.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]
