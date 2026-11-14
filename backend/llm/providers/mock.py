"""Offline provider for development and tests. Makes no network calls."""

from __future__ import annotations

from .base import LLMProvider, LLMRequest, LLMResponse


class MockProvider(LLMProvider):
    name = "mock"

    def generate(self, request: LLMRequest) -> LLMResponse:
        preview = request.user_prompt[:500]
        text = (
            "[mock response] No LLM provider is configured. "
            "Set LLM_PROVIDER to a registered provider to get real output.\n\n"
            f"Prompt preview:\n{preview}"
        )
        return LLMResponse(
            text=text,
            provider=self.name,
            model=request.model or self.default_model or "mock",
            usage={
                "input_chars": len(request.system_prompt) + len(request.user_prompt),
                "output_chars": len(text),
            },
        )
