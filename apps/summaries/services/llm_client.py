"""LLM client — OpenRouter via the OpenAI-compatible SDK.

Provider-agnostic: swap the underlying model with one env var (``LLM_MODEL``).
Returns a validated ``SummaryPayload`` or raises.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings
from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError
from pydantic import ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from apps.summaries.schemas import SummaryPayload

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are an assistant that summarizes email threads between CPA accountants and clients. "
    "Given the thread, extract three things strictly: "
    "(1) actors mentioned — people from To/From/Cc; "
    "(2) concluded discussions — topics already resolved within the thread; "
    "(3) open action items — concrete tasks still outstanding, with assignee and due_date if mentioned. "
    "Return ONLY valid JSON matching: "
    '{"actors": [{"name":"...","email":"...","role":"..."}], '
    '"conclusions": ["..."], '
    '"action_items": [{"description":"...","assignee":"...","due_date":"YYYY-MM-DD"}]}. '
    "Use null for unknown email/role/assignee/due_date. Do not invent action items if none are open."
)


class LLMError(RuntimeError):
    """Anything went wrong calling the LLM or parsing its output."""


class LLMClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.model = model or settings.LLM_MODEL
        self.timeout = timeout or settings.LLM_TIMEOUT_SEC
        api_key = api_key or settings.OPENROUTER_API_KEY
        base_url = base_url or settings.LLM_BASE_URL
        if not api_key:
            raise LLMError("OPENROUTER_API_KEY is not set.")
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=self.timeout)

    def summarize(self, *, prompt_body: str) -> SummaryPayload:
        raw = self._call(prompt_body)
        try:
            data: Any = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.exception(
                "llm.json_parse_failed",
                extra={"action": "llm.json_parse_failed", "duration_ms": "-"},
            )
            raise LLMError(f"LLM returned non-JSON output: {exc}") from exc
        try:
            return SummaryPayload.model_validate(data)
        except ValidationError as exc:
            logger.exception(
                "llm.schema_validation_failed",
                extra={"action": "llm.schema_validation_failed", "duration_ms": "-"},
            )
            raise LLMError(f"LLM output failed schema validation: {exc}") from exc

    @retry(
        retry=retry_if_exception_type(
            (APITimeoutError, APIConnectionError, RateLimitError)
        ),
        stop=stop_after_attempt(
            settings.LLM_MAX_RETRIES if hasattr(settings, "LLM_MAX_RETRIES") else 3
        ),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        reraise=True,
    )
    def _call(self, prompt_body: str) -> str:
        # Log only sizes/model — never raw email content.
        logger.info(
            "llm.request",
            extra={
                "action": "llm.request",
                "duration_ms": "-",
                "llm_model": self.model,
                "prompt_chars": len(prompt_body),
            },
        )
        resp = self._client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt_body},
            ],
        )
        text = (resp.choices[0].message.content or "").strip()
        logger.info(
            "llm.response",
            extra={
                "action": "llm.response",
                "duration_ms": "-",
                "response_chars": len(text),
            },
        )
        return text
