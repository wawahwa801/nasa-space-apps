"""Starting point for a real provider. Copy this file, then fill in ``generate``.

Steps:
1. Copy to ``llm/providers/<your_provider>.py`` and rename the class.
2. Install the provider's SDK and add it to ``backend/requirements.txt``.
3. Implement ``generate``: build the provider request from ``request``, call
   the API, and map the reply into ``LLMResponse``.
4. Catch the SDK's errors and re-raise them as ``LLMProviderError``, with
   ``retryable=True`` for rate limits, timeouts and server errors.
5. Register the class in ``llm/providers/__init__.py`` and set
   ``LLM_PROVIDER=<name>`` in ``backend/.env``.

This class is intentionally not registered.
"""

from __future__ import annotations

from .base import LLMProvider, LLMProviderError, LLMRequest, LLMResponse


class TemplateProvider(LLMProvider):
    name = "template"

    def generate(self, request: LLMRequest) -> LLMResponse:
        if not self.api_key:
            raise LLMProviderError("LLM_API_KEY is not set.")

        # client = SomeSDK(api_key=self.api_key, timeout=request.timeout_seconds)
        # reply = client.create(
        #     model=request.model or self.default_model,
        #     system=request.system_prompt,
        #     prompt=request.user_prompt,
        #     max_tokens=request.max_output_tokens,
        # )
        # return LLMResponse(
        #     text=reply.text,
        #     provider=self.name,
        #     model=reply.model,
        #     usage={"input_tokens": ..., "output_tokens": ...},
        #     raw=reply,
        # )
        raise NotImplementedError("Implement generate() for your provider.")
