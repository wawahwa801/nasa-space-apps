"""Provider registry. Register new providers here."""

from __future__ import annotations

from .base import LLMProvider, LLMProviderError, LLMRequest, LLMResponse
from .mock import MockProvider

_REGISTRY: dict[str, type[LLMProvider]] = {}


def register_provider(cls: type[LLMProvider]) -> type[LLMProvider]:
    """Add a provider class to the registry. Usable as a decorator."""
    key = cls.name.lower()
    if key in _REGISTRY and _REGISTRY[key] is not cls:
        raise ValueError(f"A provider named '{cls.name}' is already registered.")
    _REGISTRY[key] = cls
    return cls


def available_providers() -> list[str]:
    return sorted(_REGISTRY)


def create_provider(name: str, **kwargs) -> LLMProvider:
    try:
        cls = _REGISTRY[name.lower()]
    except KeyError:
        raise LLMProviderError(
            f"Unknown LLM provider '{name}'. Registered providers: {', '.join(available_providers())}."
        ) from None
    return cls(**kwargs)


register_provider(MockProvider)
# Register real providers here, for example:
# from .my_provider import MyProvider
# register_provider(MyProvider)

__all__ = [
    "LLMProvider",
    "LLMProviderError",
    "LLMRequest",
    "LLMResponse",
    "available_providers",
    "create_provider",
    "register_provider",
]
