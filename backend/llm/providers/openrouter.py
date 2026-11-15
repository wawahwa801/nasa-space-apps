"""OpenRouter provider (https://openrouter.ai), using its OpenAI-compatible
chat completions API. Standard library only: no SDK to install.

Configure in backend/.env:
    LLM_PROVIDER=openrouter
    LLM_MODEL=dots-studio/dots-3-note-preview:free
    LLM_API_KEY=<your OpenRouter key>
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Any, Callable

from .base import LLMProvider, LLMProviderError, LLMRequest, LLMResponse

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
# Sent as X-Title so the calls are labelled in the OpenRouter dashboard.
APP_TITLE = "Fire Safety Dashboard"

_STATUS_MESSAGES = {
    400: "OpenRouter rejected the request (400)",
    401: "OpenRouter rejected the API key (401). Check LLM_API_KEY in backend/.env",
    402: "The OpenRouter account has insufficient credits (402)",
    403: "OpenRouter refused the request (403); the input may have been flagged by moderation",
    404: "OpenRouter could not find the model (404). Check LLM_MODEL in backend/.env",
    408: "OpenRouter timed out (408)",
    429: "OpenRouter rate limit reached (429); free models have low limits, try again shortly",
}
_RETRYABLE = {408, 429, 500, 502, 503, 504}


def _error_detail(body: bytes) -> str:
    """The provider's own error message, shortened, or '' if there is none."""
    try:
        data = json.loads(body.decode("utf-8", "replace"))
    except ValueError:
        return ""
    err = data.get("error") if isinstance(data, dict) else None
    message = err.get("message") if isinstance(err, dict) else None
    return str(message)[:300] if message else ""


def _content_text(content: Any) -> str:
    """Message content is a string, or a list of parts for some models."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return ""


class OpenRouterProvider(LLMProvider):
    name = "openrouter"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        opener: Callable[..., Any] | None = None,
        **options: Any,
    ) -> None:
        super().__init__(api_key=api_key, model=model, **options)
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        # Injectable for tests; urlopen(request, timeout=...) otherwise.
        self._open = opener or urllib.request.urlopen

    def generate(self, request: LLMRequest) -> LLMResponse:
        if not self.api_key:
            raise LLMProviderError("LLM_API_KEY is not set. Add your OpenRouter key to backend/.env.")
        model = request.model or self.default_model
        if not model:
            raise LLMProviderError("LLM_MODEL is not set. For example: dots-studio/dots-3-note-preview:free.")

        body: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "max_tokens": request.max_output_tokens,
        }
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.json_output:
            body["response_format"] = {"type": "json_object"}

        http_request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-Title": APP_TITLE,
            },
        )
        try:
            with self._open(http_request, timeout=request.timeout_seconds) as reply:
                raw = reply.read()
        except urllib.error.HTTPError as exc:
            detail = _error_detail(exc.read() or b"")
            base = _STATUS_MESSAGES.get(exc.code, f"OpenRouter returned HTTP {exc.code}")
            raise LLMProviderError(
                f"{base}." + (f" {detail}" if detail else ""),
                retryable=exc.code in _RETRYABLE,
            ) from None
        except (urllib.error.URLError, socket.timeout, TimeoutError) as exc:
            reason = getattr(exc, "reason", exc)
            raise LLMProviderError(f"Could not reach OpenRouter: {reason}.", retryable=True) from None

        try:
            data = json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            raise LLMProviderError("OpenRouter returned a response that is not JSON.", retryable=True) from None
        # Errors can also arrive with HTTP 200 (e.g. an upstream provider failed mid-stream).
        if isinstance(data, dict) and data.get("error"):
            detail = _error_detail(raw) or "unknown error"
            raise LLMProviderError(f"OpenRouter error: {detail}", retryable=True)

        choices = data.get("choices") if isinstance(data, dict) else None
        if not choices:
            raise LLMProviderError("OpenRouter returned no choices.", retryable=True)
        choice = choices[0]
        text = _content_text((choice.get("message") or {}).get("content")).strip()
        if not text:
            # Reasoning models spend output tokens thinking before they answer.
            if choice.get("finish_reason") == "length":
                raise LLMProviderError(
                    "The model ran out of output tokens before answering. Raise LLM_MAX_OUTPUT_TOKENS in backend/.env."
                )
            raise LLMProviderError("The model returned an empty answer.", retryable=True)

        usage_in = data.get("usage") or {}
        usage = {
            key: int(usage_in[src])
            for key, src in (("input_tokens", "prompt_tokens"), ("output_tokens", "completion_tokens"))
            if isinstance(usage_in.get(src), (int, float))
        }
        return LLMResponse(text=text, provider=self.name, model=data.get("model") or model, usage=usage)
