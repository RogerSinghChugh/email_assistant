"""Client data access — firm-scoped reads with superuser bypass."""

from django.db.models import Q, QuerySet

from apps.clients.models import Client


class ClientRepository:
    @staticmethod
    def list_for_firm(
        firm_id, *, is_superuser: bool = False, search: str | None = None
    ) -> QuerySet[Client]:
        qs = (
            Client.objects.all()
            if is_superuser
            else Client.objects.filter(firm_id=firm_id)
        )
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(email__icontains=search))
        return qs.select_related("firm")

    @staticmethod
    def get_for_firm(client_id, firm_id, *, is_superuser: bool = False) -> Client:
        if is_superuser:
            return Client.objects.select_related("firm").get(pk=client_id)
        return Client.objects.select_related("firm").get(pk=client_id, firm_id=firm_id)
