"""Thread list + detail views."""

from django.db.models import Count
from django.http import Http404
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated

from apps.core.permissions import IsInSameFirm
from apps.emails.models import EmailThread
from apps.emails.repositories import ThreadRepository
from apps.emails.serializers import (
    EmailThreadDetailSerializer,
    EmailThreadListSerializer,
)


def _is_superuser(user) -> bool:
    return bool(getattr(user, "is_role_superuser", False))


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
