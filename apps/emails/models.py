"""Email thread + message models. Subject and body are encrypted at rest."""

from django.db import models
from encrypted_fields.fields import EncryptedCharField, EncryptedTextField

from apps.core.models import TimeStampedUUIDModel


class EmailThread(TimeStampedUUIDModel):
    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.CASCADE,
        related_name="threads",
    )
    # Denormalized from client.firm_id — primary AuthZ + reporting filter.
    firm = models.ForeignKey(
        "accounts.Firm",
        on_delete=models.CASCADE,
        related_name="email_threads",
    )
    encrypted_subject = EncryptedCharField(max_length=998, blank=True, default="")
    external_thread_id = models.CharField(max_length=255, unique=True)
    first_message_at = models.DateTimeField()
    last_message_at = models.DateTimeField()
    # Set at summary-refresh time to the max sent_at seen. Used by SummaryReadSerializer.is_stale.
    up_to_message_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-last_message_at",)
        indexes = [
            models.Index(fields=["client", "-last_message_at"]),
            models.Index(fields=["firm"]),
        ]

    def __str__(self) -> str:
        return f"Thread<{self.external_thread_id}>"


class EmailMessage(TimeStampedUUIDModel):
    thread = models.ForeignKey(
        EmailThread,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    # Denormalized for fast AuthZ + reporting without joining through thread.
    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.CASCADE,
        related_name="messages",
    )
    firm = models.ForeignKey(
        "accounts.Firm",
        on_delete=models.CASCADE,
        related_name="email_messages",
    )
    external_message_id = models.CharField(max_length=255, unique=True)
    sender_email = models.EmailField()
    # {"to": ["a@x.com", ...], "cc": [...]} — cleartext for actor extraction + filtering.
    recipients = models.JSONField(default=dict)
    encrypted_body = EncryptedTextField(blank=True, default="")
    sent_at = models.DateTimeField()

    class Meta:
        ordering = ("sent_at",)
        indexes = [
            models.Index(fields=["thread", "sent_at"]),
            models.Index(fields=["firm"]),
            models.Index(fields=["client"]),
        ]

    def __str__(self) -> str:
        return f"Message<{self.external_message_id}>"
