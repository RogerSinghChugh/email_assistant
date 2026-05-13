"""SummaryService — refresh flow with mocked LLM."""

from unittest.mock import MagicMock

from django.test import TestCase
from django.utils import timezone

from apps.summaries.models import EmailSummary
from apps.summaries.schemas import ActionItem, Actor, SummaryPayload
from apps.summaries.services.summarizer import SummaryService
from tests.factories import EmailMessageFactory, EmailThreadFactory


class SummarizerTests(TestCase):
    def setUp(self):
        self.thread = EmailThreadFactory()
        self.messages = [
            EmailMessageFactory(
                thread=self.thread,
                client=self.thread.client,
                firm=self.thread.firm,
                sender_email="client@x.com",
                encrypted_body="Need help with Q4 forms.",
                sent_at=timezone.now() - timezone.timedelta(hours=2),
            ),
            EmailMessageFactory(
                thread=self.thread,
                client=self.thread.client,
                firm=self.thread.firm,
                sender_email="cpa@y.com",
                encrypted_body="Sure, sending shortly.",
                sent_at=timezone.now() - timezone.timedelta(hours=1),
            ),
        ]
        self.fake_payload = SummaryPayload(
            actors=[Actor(name="Client X", email="client@x.com", role="client")],
            conclusions=["CPA acknowledged the request."],
            action_items=[ActionItem(description="Send Q4 forms", assignee="cpa")],
        )

    def _service_with_mock(self):
        fake_llm = MagicMock()
        fake_llm.summarize.return_value = self.fake_payload
        return SummaryService(llm=fake_llm), fake_llm

    def test_refresh_creates_summary_with_encrypted_payload(self):
        service, fake = self._service_with_mock()
        result = service.refresh(self.thread.id)

        self.assertEqual(result.emails_analyzed, 2)
        summary = EmailSummary.objects.get(thread_id=self.thread.id)
        self.assertEqual(summary.firm_id, self.thread.firm_id)
        self.assertEqual(
            summary.encrypted_payload["action_items"][0]["description"],
            "Send Q4 forms",
        )
        fake.summarize.assert_called_once()

    def test_refresh_sets_up_to_message_at(self):
        service, _ = self._service_with_mock()
        service.refresh(self.thread.id)
        summary = EmailSummary.objects.get(thread_id=self.thread.id)
        max_sent = max(m.sent_at for m in self.messages)
        self.assertEqual(summary.up_to_message_at, max_sent)

    def test_refresh_is_upsert(self):
        service, _ = self._service_with_mock()
        first = service.refresh(self.thread.id)
        second = service.refresh(self.thread.id)
        self.assertEqual(first.summary.pk, second.summary.pk)
        self.assertEqual(EmailSummary.objects.filter(thread=self.thread).count(), 1)

    def test_refresh_raises_on_empty_thread(self):
        empty_thread = EmailThreadFactory()
        service, _ = self._service_with_mock()
        with self.assertRaises(ValueError):
            service.refresh(empty_thread.id)
