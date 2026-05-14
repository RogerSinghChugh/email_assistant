"""SummaryService — orchestrates LLM call + persistence.

Full re-summarization on each refresh (incremental flagged as future work).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.core.logging import log_action
from apps.emails.models import EmailMessage, EmailThread
from apps.summaries.models import EmailSummary
from apps.summaries.repositories import SummaryRepository
from apps.summaries.schemas import SummaryPayload
from apps.summaries.services.cache import invalidate_summary
from apps.summaries.services.llm_client import LLMClient
from apps.summaries.services.prompts import build_user_prompt

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

        prompt = build_user_prompt(thread, messages)
        payload = self._llm.summarize(prompt_body=prompt)

        up_to = max(m.sent_at for m in messages)

        # Atomic write + post-commit cache invalidation.
        # Doing the invalidate inside ``transaction.on_commit`` closes the
        # classic write-then-invalidate race: until the row is durable, the
        # cache must NOT be cleared (a reader between the clear and the commit
        # would repopulate from the old DB state and leave stale cache). With
        # on_commit, the delete fires only after the upsert is visible.
        with transaction.atomic():
            summary = SummaryRepository.upsert(
                thread_id=thread.id,
                firm_id=thread.firm_id,
                payload=payload.model_dump(mode="json"),
                emails_analyzed=len(messages),
                last_refreshed_at=timezone.now(),
                up_to_message_at=up_to,
            )
            transaction.on_commit(lambda: invalidate_summary(thread.id))

        return RefreshResult(
            summary=summary, payload=payload, emails_analyzed=len(messages)
        )
