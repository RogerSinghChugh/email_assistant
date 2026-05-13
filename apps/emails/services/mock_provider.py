"""Mock email provider — reads from seeded DB rows.

Same shape any future ``GraphEmailProvider`` (Microsoft Graph) would honor, so the
summarization pipeline doesn't change when the provider swaps.
"""

from datetime import datetime

from apps.emails.models import EmailMessage
from apps.emails.services.provider_base import EmailProvider, ProviderMessage


class MockEmailProvider(EmailProvider):
    def list_messages(
        self, client_id, *, since: datetime | None = None
    ) -> list[ProviderMessage]:
        qs = EmailMessage.objects.filter(client_id=client_id).order_by("sent_at")
        if since is not None:
            qs = qs.filter(sent_at__gte=since)
        return [
            ProviderMessage(
                external_message_id=m.external_message_id,
                external_thread_id=m.thread.external_thread_id,
                sender_email=m.sender_email,
                recipients_to=list(m.recipients.get("to", [])),
                recipients_cc=list(m.recipients.get("cc", [])),
                subject=m.thread.encrypted_subject,  # decrypted by the field on read
                body=m.encrypted_body,
                sent_at=m.sent_at,
            )
            for m in qs.select_related("thread")
        ]
