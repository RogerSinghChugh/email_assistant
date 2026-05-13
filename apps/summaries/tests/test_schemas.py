"""Pydantic SummaryPayload validation."""

from django.test import SimpleTestCase
from pydantic import ValidationError

from apps.summaries.schemas import ActionItem, Actor, SummaryPayload


class PydanticSchemaTests(SimpleTestCase):
    def test_accepts_minimal_valid(self):
        p = SummaryPayload.model_validate(
            {"actors": [], "conclusions": [], "action_items": []},
        )
        self.assertEqual(p.actors, [])
        self.assertEqual(p.conclusions, [])
        self.assertEqual(p.action_items, [])

    def test_accepts_full_payload(self):
        data = {
            "actors": [{"name": "Jane Doe", "email": "j@x.com", "role": "client"}],
            "conclusions": ["Tax forms received."],
            "action_items": [
                {
                    "description": "Send K-1",
                    "assignee": "cpa",
                    "due_date": "2026-04-15",
                },
            ],
        }
        p = SummaryPayload.model_validate(data)
        self.assertEqual(p.actors[0].name, "Jane Doe")
        self.assertEqual(p.action_items[0].description, "Send K-1")

    def test_rejects_missing_required_actor_name(self):
        with self.assertRaises(ValidationError):
            Actor.model_validate({"email": "j@x.com"})

    def test_rejects_action_item_without_description(self):
        with self.assertRaises(ValidationError):
            ActionItem.model_validate({"assignee": "cpa"})

    def test_optional_fields_default_to_none(self):
        a = Actor.model_validate({"name": "Solo"})
        self.assertIsNone(a.email)
        self.assertIsNone(a.role)
