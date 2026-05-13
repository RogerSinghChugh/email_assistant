"""SummaryService — orchestrates LLM call + persistence.

Full re-summarization on each refresh (incremental flagged as future work).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.utils import timezone

from apps.core.logging import log_action
from apps.emails.models import EmailMessage, EmailThread
from apps.summaries.models import EmailSummary
from apps.summaries.repositories import SummaryRepository
from apps.summaries.schemas import SummaryPayload
from apps.summaries.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RefreshResult:
    summary: EmailSummary
    payload: SummaryPayload
    emails_analyzed: int


class SummaryService:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self._llm = llm or LLMClient()

    @log_action("summary.refresh")
    def refresh(self, thread_id) -> RefreshResult:
        thread = EmailThread.objects.select_related("firm", "client").get(pk=thread_id)
        messages = list(
            EmailMessage.objects.filter(thread_id=thread_id).order_by("sent_at")
        )
        if not messages:
            raise ValueError(f"Thread {thread_id} has no messages.")

        prompt = self._build_prompt(thread, messages)
        payload = self._llm.summarize(prompt_body=prompt)

        up_to = max(m.sent_at for m in messages)
        summary = SummaryRepository.upsert(
            thread_id=thread.id,
            firm_id=thread.firm_id,
            payload=payload.model_dump(mode="json"),
            emails_analyzed=len(messages),
            last_refreshed_at=timezone.now(),
            up_to_message_at=up_to,
        )
        return RefreshResult(
            summary=summary, payload=payload, emails_analyzed=len(messages)
        )

    @staticmethod
    def _build_prompt(thread: EmailThread, messages: list[EmailMessage]) -> str:
        lines = [
            f"Subject: {thread.encrypted_subject}",
            f"Client: {thread.client.name} <{thread.client.email}>",
            "",
            "MESSAGES (oldest first):",
        ]
        for i, m in enumerate(messages, start=1):
            to = ", ".join(m.recipients.get("to", []))
            cc = ", ".join(m.recipients.get("cc", []))
            lines.append(
                f"\n--- Message {i} ({m.sent_at.isoformat()}) ---\n"
                f"From: {m.sender_email}\nTo: {to}\nCc: {cc}\n\n{m.encrypted_body}"
            )
        return "\n".join(lines)
