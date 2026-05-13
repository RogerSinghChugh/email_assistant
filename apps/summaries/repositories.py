"""Summary data access."""

from apps.summaries.models import EmailSummary


class SummaryRepository:
    @staticmethod
    def get_or_none(thread_id) -> EmailSummary | None:
        return EmailSummary.objects.filter(thread_id=thread_id).first()

    @staticmethod
    def upsert(
        *,
        thread_id,
        firm_id,
        payload: dict,
        emails_analyzed: int,
        last_refreshed_at,
        up_to_message_at,
    ) -> EmailSummary:
        obj, _ = EmailSummary.objects.update_or_create(
            thread_id=thread_id,
            defaults={
                "firm_id": firm_id,
                "encrypted_payload": payload,
                "emails_analyzed": emails_analyzed,
                "last_refreshed_at": last_refreshed_at,
                "up_to_message_at": up_to_message_at,
            },
        )
        return obj
