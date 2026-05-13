"""Thread + message data access — firm-scoped reads."""

from django.db.models import QuerySet

from apps.emails.models import EmailMessage, EmailThread


class ThreadRepository:
    @staticmethod
    def list_for_client(
        client_id, firm_id, *, is_superuser: bool = False
    ) -> QuerySet[EmailThread]:
        qs = EmailThread.objects.filter(client_id=client_id)
        if not is_superuser:
            qs = qs.filter(firm_id=firm_id)
        return qs.select_related("client", "firm")

    @staticmethod
    def list_for_firm(firm_id, *, is_superuser: bool = False) -> QuerySet[EmailThread]:
        qs = (
            EmailThread.objects.all()
            if is_superuser
            else EmailThread.objects.filter(firm_id=firm_id)
        )
        return qs.select_related("client", "firm")

    @staticmethod
    def get_for_firm(thread_id, firm_id, *, is_superuser: bool = False) -> EmailThread:
        if is_superuser:
            return EmailThread.objects.select_related("client", "firm").get(
                pk=thread_id
            )
        return EmailThread.objects.select_related("client", "firm").get(
            pk=thread_id, firm_id=firm_id
        )


class MessageRepository:
    @staticmethod
    def list_for_thread(
        thread_id, firm_id, *, is_superuser: bool = False
    ) -> QuerySet[EmailMessage]:
        qs = EmailMessage.objects.filter(thread_id=thread_id)
        if not is_superuser:
            qs = qs.filter(firm_id=firm_id)
        return qs.order_by("sent_at")
