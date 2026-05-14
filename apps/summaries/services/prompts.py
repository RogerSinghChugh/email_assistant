"""LLM prompts for thread summarization.

Both the system message and the user-message builder live here so prompt
iteration touches a single file. The system prompt establishes contract and
inference rules; the user prompt provides per-thread context (today's date,
client identity, ordered messages).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils import timezone

if TYPE_CHECKING:
    from apps.emails.models import EmailMessage, EmailThread


SYSTEM_PROMPT = (
    "You are an assistant that summarizes email threads between CPA accountants and clients. "
    "Given the thread, extract three things strictly: "
    "(1) actors mentioned — every distinct person from From/To/Cc; "
    "(2) concluded discussions — topics already resolved within the thread; "
    "(3) open action items — concrete tasks still outstanding, with assignee and due_date if mentioned. "
    "Return ONLY valid JSON matching: "
    '{"actors": [{"name":"...","email":"...","role":"..."}], '
    '"conclusions": ["..."], '
    '"action_items": [{"description":"...","assignee":"...","due_date":"YYYY-MM-DD"}]}. '
    "Rules: "
    '(a) Each actor\'s `role` MUST be either "client" or "accountant". The thread header gives the '
    "client's email — anyone with that email is the client; everyone else is an accountant from the CPA firm. "
    "Never leave role null. "
    '(b) For `due_date`, resolve relative phrasings ("by April 15", "original April deadline", "end of month") '
    "to an absolute YYYY-MM-DD using `today` from the thread header. If a date is mentioned with no year, "
    "pick the next future occurrence relative to today. Use null only if no date is implied at all. "
    "(c) Use null for unknown email/assignee. Do not invent action items if none are open."
)


def build_user_prompt(thread: "EmailThread", messages: list["EmailMessage"]) -> str:
    """Render the per-thread user message. `today` is injected so the model can resolve relative dates."""
    today = timezone.now().date().isoformat()
    lines = [
        f"Today: {today}",
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
