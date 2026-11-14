"""LLM settings read from environment variables (see backend/.env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"{name} must be an integer, got '{value}'.") from None


def _float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"{name} must be a number, got '{value}'.") from None


@dataclass(frozen=True)
class LLMSettings:
    provider: str = "mock"
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    max_output_tokens: int = 1024
    timeout_seconds: float = 60.0
    max_input_chars: int = 50_000

    @classmethod
    def from_env(cls) -> "LLMSettings":
        return cls(
            provider=os.getenv("LLM_PROVIDER", "mock").strip() or "mock",
            model=os.getenv("LLM_MODEL") or None,
            api_key=os.getenv("LLM_API_KEY") or None,
            base_url=os.getenv("LLM_BASE_URL") or None,
            max_output_tokens=_int("LLM_MAX_OUTPUT_TOKENS", 1024),
            timeout_seconds=_float("LLM_TIMEOUT_SECONDS", 60.0),
            max_input_chars=_int("LLM_MAX_INPUT_CHARS", 50_000),
        )
