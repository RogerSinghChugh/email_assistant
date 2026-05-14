"""Refresh fan-in: concurrent triggers share a task_id."""

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.summaries.schemas import SummaryPayload
from apps.summaries.services.cache import inflight_key
from tests.factories import AccountantFactory, EmailMessageFactory, EmailThreadFactory


class RefreshDedupTests(TestCase):
    def setUp(self):
        self.user = AccountantFactory()
        self.thread = EmailThreadFactory(firm=self.user.firm)
        EmailMessageFactory(
            thread=self.thread, client=self.thread.client, firm=self.thread.firm
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        cache.clear()

    def _mock_llm(self):
        fake = SummaryPayload(actors=[], conclusions=[], action_items=[])
        return patch(
            "apps.summaries.services.summarizer.LLMClient",
            return_value=type("M", (), {"summarize": lambda self, **kw: fake})(),
        )

    def test_first_refresh_claims_inflight_returns_joined_false(self):
        cache.delete(inflight_key(str(self.thread.id)))
        with self._mock_llm():
            resp = self.client.post(f"/api/threads/{self.thread.id}/summary/refresh/")
        self.assertEqual(resp.status_code, 202)
        body = resp.json()
        self.assertIn("task_id", body)
        self.assertFalse(body["joined"])

    def test_concurrent_refresh_joins_existing_task(self):
        # Simulate "someone else's refresh just started" by pre-seeding the key.
        existing_task_id = "11111111-1111-1111-1111-111111111111"
        cache.set(inflight_key(str(self.thread.id)), existing_task_id, timeout=120)

        with self._mock_llm():
            resp = self.client.post(f"/api/threads/{self.thread.id}/summary/refresh/")

        self.assertEqual(resp.status_code, 202)
        body = resp.json()
        self.assertEqual(body["task_id"], existing_task_id)
        self.assertTrue(body["joined"])
        self.assertIn(existing_task_id, body["status_url"])
