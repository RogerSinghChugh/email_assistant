"""Encryption round-trip through the ORM fields."""

from django.test import TestCase
from django.utils import timezone

from tests.factories import EmailMessageFactory, EmailSummaryFactory, EmailThreadFactory


class EncryptionRoundTripTests(TestCase):
    def test_thread_subject_round_trips(self):
        thread = EmailThreadFactory(encrypted_subject="Q4 tax review")
        reloaded = type(thread).objects.get(pk=thread.pk)
        self.assertEqual(reloaded.encrypted_subject, "Q4 tax review")

    def test_message_body_round_trips(self):
        msg = EmailMessageFactory(encrypted_body="Please send the K-1s.")
        reloaded = type(msg).objects.get(pk=msg.pk)
        self.assertEqual(reloaded.encrypted_body, "Please send the K-1s.")

    def test_summary_payload_round_trips(self):
        payload = {
            "actors": [{"name": "Jane Doe", "email": "j@x.com", "role": "client"}],
            "conclusions": ["Q4 forms received."],
            "action_items": [
                {
                    "description": "File 1040",
                    "assignee": "cpa",
                    "due_date": "2026-04-15",
                },
            ],
        }
        summary = EmailSummaryFactory(
            encrypted_payload=payload,
            emails_analyzed=3,
            last_refreshed_at=timezone.now(),
        )
        reloaded = type(summary).objects.get(pk=summary.pk)
        self.assertEqual(reloaded.encrypted_payload, payload)

    def test_ciphertext_stored_in_db(self):
        """Sanity-check: raw DB column should NOT match plaintext."""
        from django.db import connection

        EmailMessageFactory(encrypted_body="topsecret-marker-xyz")
        with connection.cursor() as cur:
            cur.execute(
                "SELECT encrypted_body FROM emails_emailmessage "
                "ORDER BY sent_at DESC LIMIT 1"
            )
            raw = cur.fetchone()[0]
        self.assertNotIn("topsecret-marker-xyz", raw)
        # Fernet ciphertexts start with the version byte 0x80 → base64 begins with 'gAAAA'.
        self.assertTrue(raw.startswith("gAAAA"))
