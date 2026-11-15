"""Offline provider for development and tests. Makes no network calls."""

from __future__ import annotations

import json

from .base import LLMProvider, LLMRequest, LLMResponse

# Canned safety insight so the dashboard card works offline.
MOCK_INSIGHT = {
    "headline": "Mock insight: no LLM provider is configured.",
    "risk_level": "unknown",
    "summary": "This is placeholder text from the offline mock provider. Set LLM_PROVIDER=openrouter, "
    "LLM_MODEL and LLM_API_KEY in backend/.env to get a real reading of the safety report.",
    "concerns": [],
    "checks": ["Configure the OpenRouter key in backend/.env, restart the backend, and generate again."],
    "data_gaps": [],
}


class MockProvider(LLMProvider):
    name = "mock"

    def generate(self, request: LLMRequest) -> LLMResponse:
        if request.json_output:
            text = json.dumps(MOCK_INSIGHT)
            return LLMResponse(text=text, provider=self.name, model=request.model or self.default_model or "mock")
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
