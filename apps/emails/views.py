"""Thread list + detail views."""

from django.db.models import Count
from django.http import Http404
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsInSameFirm
from apps.emails.models import EmailThread
from apps.emails.repositories import ThreadRepository
from apps.emails.serializers import (
    EmailThreadDetailSerializer,
    EmailThreadListSerializer,
)


def _is_superuser(user) -> bool:
    return bool(getattr(user, "is_role_superuser", False))


SAMPLE_LIMIT = 8


class ClientThreadListView(ListAPIView):
    """GET /api/clients/{client_id}/threads/ — list this client's threads."""

    serializer_class = EmailThreadListSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return ThreadRepository.list_for_client(
            client_id=self.kwargs["client_id"],
            firm_id=self.request.user.firm_id,
            is_superuser=_is_superuser(self.request.user),
        ).annotate(message_count=Count("messages"))


class SampleThreadListView(APIView):
    """GET /api/threads/sample/ — small pick-list for the demo UI.

    Returns the user's most recent threads (or cross-firm for superuser) so the
    UI can offer clickable thread chips instead of forcing the reviewer to
    copy UUIDs from the seed_data terminal output.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        responses=inline_serializer(
            name="SampleThread",
            many=True,
            fields={
                "id": drf_serializers.UUIDField(),
                "subject": drf_serializers.CharField(),
                "client_name": drf_serializers.CharField(),
                "firm_name": drf_serializers.CharField(),
                "last_message_at": drf_serializers.DateTimeField(),
            },
        ),
    )
    def get(self, request):
        qs = ThreadRepository.list_for_firm(
            firm_id=request.user.firm_id,
            is_superuser=_is_superuser(request.user),
        )[:SAMPLE_LIMIT]
        data = [
            {
                "id": str(t.id),
                "subject": t.encrypted_subject or "(no subject)",
                "client_name": t.client.name,
                "firm_name": t.firm.name,
                "last_message_at": t.last_message_at,
            }
            for t in qs
        ]
        return Response(data)


class ThreadDetailView(RetrieveAPIView):
    """GET /api/threads/{id}/ — thread + ordered messages."""

    serializer_class = EmailThreadDetailSerializer
    permission_classes = (IsAuthenticated, IsInSameFirm)
    lookup_field = "pk"

    def get_object(self):
        try:
            obj = ThreadRepository.get_for_firm(
                thread_id=self.kwargs["pk"],
                firm_id=self.request.user.firm_id,
                is_superuser=_is_superuser(self.request.user),
            )
        except EmailThread.DoesNotExist as exc:
            raise Http404 from exc
        self.check_object_permissions(self.request, obj)
        return obj
