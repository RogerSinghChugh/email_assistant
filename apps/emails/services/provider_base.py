"""Email-provider protocol. The mock and (future) real Graph adapter both satisfy this."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class ProviderMessage:
    """Normalized message shape returned by any provider."""

    external_message_id: str
    external_thread_id: str
    sender_email: str
    recipients_to: list[str]
    recipients_cc: list[str]
    subject: str
    body: str
    sent_at: datetime


class EmailProvider(Protocol):
    """Implementations: ``MockEmailProvider`` (DB-backed), future ``GraphEmailProvider`` (Microsoft Graph)."""

    def list_messages(
        self, client_id, *, since: datetime | None = None
    ) -> list[ProviderMessage]:
        """Return all messages for a client, optionally filtered by sent_at >= since."""
        ...
