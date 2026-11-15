"""Provider-neutral contract that every LLM integration implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class LLMProviderError(Exception):
    """Raised when a provider cannot produce a response.

    ``retryable`` tells callers whether trying again later may succeed
    (rate limits, timeouts, temporary outages) or not (bad credentials,
    invalid request).
    """

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class LLMRequest:
    """Everything a provider needs to make one call."""

    system_prompt: str
    user_prompt: str
    model: str | None = None
    max_output_tokens: int = 1024
    timeout_seconds: float = 60.0
    # Ask for a JSON object (providers that support it enforce the format).
    json_output: bool = False
    # None leaves the provider's default.
    temperature: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    """Normalized result returned by every provider."""

    text: str
    provider: str
    model: str | None = None
    usage: dict[str, int] = field(default_factory=dict)
    raw: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "provider": self.provider,
            "model": self.model,
            "usage": self.usage,
        }


class LLMProvider(ABC):
    """Base class for LLM integrations.

    To add a provider, subclass this, implement ``generate``, and register
    it in ``llm/providers/__init__.py``. Translate any SDK or HTTP errors
    into ``LLMProviderError`` so the API layer can report them uniformly.
    """

    name: str = "base"

    def __init__(self, *, api_key: str | None = None, model: str | None = None, **options: Any) -> None:
        self.api_key = api_key
        self.default_model = model
        self.options = options

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Send one request to the model and return its normalized response."""
