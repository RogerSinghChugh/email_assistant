"""Pydantic schema for Gemini/LLM structured output.

Used to validate the JSON that comes back from the model before persisting. Keeps
the LLM/HTTP boundary honest — if the model returns garbage, we fail loudly rather
than storing invalid data.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Actor(BaseModel):
    name: str = Field(description="Person or organization mentioned in the thread.")
    email: str | None = Field(
        default=None, description="Email if known from to/from/cc."
    )
    role: str | None = Field(
        default=None,
        description='One of "client", "accountant", or "external" if inferable.',
    )


class ActionItem(BaseModel):
    description: str = Field(description="Single, concrete open task.")
    assignee: str | None = Field(
        default=None, description="Name or email of who should act."
    )
    due_date: str | None = Field(
        default=None, description="ISO date (YYYY-MM-DD) if mentioned."
    )


class SummaryPayload(BaseModel):
    """The structured summary persisted (encrypted) in EmailSummary.encrypted_payload."""

    actors: list[Actor] = Field(default_factory=list)
    conclusions: list[str] = Field(
        default_factory=list,
        description="Discussions that have been resolved/concluded.",
    )
    action_items: list[ActionItem] = Field(
        default_factory=list,
        description="Open items that still require action.",
    )
