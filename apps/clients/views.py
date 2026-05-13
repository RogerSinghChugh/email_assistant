"""Client read endpoints — firm-scoped."""

from django.http import Http404
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated

from apps.clients.models import Client
from apps.clients.repositories import ClientRepository
from apps.clients.serializers import ClientSerializer
from apps.core.permissions import IsInSameFirm


def _is_superuser(user) -> bool:
    return bool(getattr(user, "is_role_superuser", False))


class ClientListView(ListAPIView):
    serializer_class = ClientSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return ClientRepository.list_for_firm(
            firm_id=self.request.user.firm_id,
            is_superuser=_is_superuser(self.request.user),
            search=self.request.query_params.get("search"),
        )


class ClientDetailView(RetrieveAPIView):
    serializer_class = ClientSerializer
    permission_classes = (IsAuthenticated, IsInSameFirm)
    queryset = (
        Client.objects.all()
    )  # IsInSameFirm enforces firm scope via object permission

    def get_object(self):
        try:
            obj = ClientRepository.get_for_firm(
                client_id=self.kwargs["pk"],
                firm_id=self.request.user.firm_id,
                is_superuser=_is_superuser(self.request.user),
            )
        except Client.DoesNotExist as exc:
            raise Http404 from exc
        self.check_object_permissions(self.request, obj)
        return obj
