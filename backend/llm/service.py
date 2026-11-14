"""Orchestrates one analysis: validate input -> build prompt -> call provider."""

from __future__ import annotations

from typing import Any

from .config import LLMSettings
from .input_processing import InputValidationError, process_input
from .prompts import SYSTEM_PROMPT, build_user_prompt
from .providers import LLMProvider, LLMRequest, create_provider

MAX_TEXT_FIELD_CHARS = 4_000


def _optional_text(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise InputValidationError(f"'{key}' must be a string.")
    if len(value) > MAX_TEXT_FIELD_CHARS:
        raise InputValidationError(f"'{key}' must be at most {MAX_TEXT_FIELD_CHARS:,} characters.")
    return value


class AnalysisService:
    def __init__(self, settings: LLMSettings, provider: LLMProvider | None = None) -> None:
        self.settings = settings
        self.provider = provider or create_provider(
            settings.provider,
            api_key=settings.api_key,
            model=settings.model,
            base_url=settings.base_url,
        )

    def analyze(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise InputValidationError("Request body must be a JSON object.")

        processed = process_input(
            payload.get("data"),
            payload.get("data_type", "auto"),
            max_chars=self.settings.max_input_chars,
        )
        request = LLMRequest(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=build_user_prompt(
                processed,
                _optional_text(payload, "instructions"),
                _optional_text(payload, "context"),
            ),
            model=self.settings.model,
            max_output_tokens=self.settings.max_output_tokens,
            timeout_seconds=self.settings.timeout_seconds,
        )
        response = self.provider.generate(request)
        return {
            "output": response.text,
            "provider": response.provider,
            "model": response.model,
            "usage": response.usage,
            "input": {
                "data_type": processed.data_type,
                "shape": processed.shape,
                "summary": processed.summary,
            },
        }
