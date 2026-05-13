"""Cross-firm AuthZ: accountants in firm A cannot read firm B's resources.

Superusers bypass the scope and see both.
"""

from unittest.mock import patch

from rest_framework.test import APITestCase

from apps.accounts.models import RoleChoices
from apps.summaries.schemas import SummaryPayload
from tests.factories import (
    AccountantFactory,
    ClientFactory,
    EmailMessageFactory,
    EmailThreadFactory,
    FirmFactory,
)


class CrossFirmAuthZTests(APITestCase):
    def setUp(self):
        self.firm_a = FirmFactory(name="Firm A")
        self.firm_b = FirmFactory(name="Firm B")
        self.user_a = AccountantFactory(firm=self.firm_a)
        self.user_b = AccountantFactory(firm=self.firm_b)
        self.super = AccountantFactory(
            firm=None,
            role=RoleChoices.SUPERUSER,
            is_staff=True,
            is_superuser=True,
        )

        self.client_a = ClientFactory(firm=self.firm_a)
        self.thread_a = EmailThreadFactory(client=self.client_a, firm=self.firm_a)
        EmailMessageFactory(
            thread=self.thread_a,
            client=self.client_a,
            firm=self.firm_a,
        )

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def test_user_b_cannot_list_firm_a_client(self):
        self._auth(self.user_b)
        resp = self.client.get(f"/api/clients/{self.client_a.pk}/")
        self.assertEqual(resp.status_code, 404)

    def test_user_b_cannot_fetch_firm_a_thread(self):
        self._auth(self.user_b)
        resp = self.client.get(f"/api/threads/{self.thread_a.pk}/")
        self.assertIn(resp.status_code, (403, 404))

    def test_user_a_can_fetch_own_thread(self):
        self._auth(self.user_a)
        resp = self.client.get(f"/api/threads/{self.thread_a.pk}/")
        self.assertEqual(resp.status_code, 200)

    def test_summary_refresh_cross_firm_is_404(self):
        self._auth(self.user_b)
        resp = self.client.post(f"/api/threads/{self.thread_a.pk}/summary/refresh/")
        self.assertEqual(resp.status_code, 404)

    def test_summary_get_404_when_not_generated(self):
        self._auth(self.user_a)
        resp = self.client.get(f"/api/threads/{self.thread_a.pk}/summary/")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("refresh_url", resp.json())

    def test_summary_get_200_after_refresh(self):
        self._auth(self.user_a)
        fake = SummaryPayload(actors=[], conclusions=[], action_items=[])
        with patch("apps.summaries.services.summarizer.LLMClient") as MockLLM:
            MockLLM.return_value.summarize.return_value = fake
            r1 = self.client.post(f"/api/threads/{self.thread_a.pk}/summary/refresh/")
            self.assertEqual(r1.status_code, 202)
        r2 = self.client.get(f"/api/threads/{self.thread_a.pk}/summary/")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["emails_analyzed"], 1)

    def test_superuser_can_fetch_any_firm_thread(self):
        self._auth(self.super)
        resp = self.client.get(f"/api/threads/{self.thread_a.pk}/")
        self.assertEqual(resp.status_code, 200)

    def test_member_cannot_access_firm_report(self):
        self._auth(self.user_a)
        resp = self.client.get("/api/reports/firm/")
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_access_firm_report(self):
        admin = AccountantFactory(firm=self.firm_a, role=RoleChoices.ADMIN)
        self._auth(admin)
        resp = self.client.get("/api/reports/firm/")
        self.assertEqual(resp.status_code, 200)

    def test_member_cannot_access_global_report(self):
        admin = AccountantFactory(firm=self.firm_a, role=RoleChoices.ADMIN)
        self._auth(admin)
        resp = self.client.get("/api/reports/global/")
        self.assertEqual(resp.status_code, 403)

    def test_superuser_can_access_global_report(self):
        self._auth(self.super)
        resp = self.client.get("/api/reports/global/")
        self.assertEqual(resp.status_code, 200)
