"""EmailSummary — encrypted at rest, one per thread, denormalized firm_id."""

from django.db import models
from encrypted_fields.fields import EncryptedJSONField

from apps.core.models import TimeStampedUUIDModel


class EmailSummary(TimeStampedUUIDModel):
    thread = models.OneToOneField(
        "emails.EmailThread",
        on_delete=models.CASCADE,
        related_name="summary",
    )
    # Denormalized — primary AuthZ filter for reads and the grouping key for reports.
    firm = models.ForeignKey(
        "accounts.Firm",
        on_delete=models.CASCADE,
        related_name="email_summaries",
    )
    encrypted_payload = EncryptedJSONField(default=dict)
    emails_analyzed = models.PositiveIntegerField(default=0)
    last_refreshed_at = models.DateTimeField()
    # Max sent_at across messages at refresh time. Used to compute `is_stale` on read.
    up_to_message_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["firm"]),
            models.Index(fields=["last_refreshed_at"]),
        ]

    def __str__(self) -> str:
        return f"Summary<{self.thread_id}>"
