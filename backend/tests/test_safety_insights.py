import io
import json
import urllib.error

import pytest

from app import create_app
from llm import AnalysisService, LLMProvider, LLMProviderError, LLMRequest, LLMResponse, LLMSettings, parse_insight
from llm.providers.openrouter import OpenRouterProvider

REPORT = {
    "inputs": {"o2_pct": 21.5, "co_ppm": 60, "material_types": ["PMMA (acrylic)"]},
    "assessment": [{"level": "serious", "title": "Carbon monoxide elevated", "detail": "<strong>60 ppm</strong>"}],
}
INSIGHT = {
    "headline": "CO is rising quickly.",
    "risk_level": "serious",
    "summary": "CO is 60 ppm.",
    "concerns": [{"title": "CO", "level": "serious", "explanation": "60 ppm", "action": "Check the area"}],
    "checks": ["Check the CO sensor"],
    "data_gaps": ["No CO2 reading"],
}


class StubProvider(LLMProvider):
    name = "stub"

    def __init__(self, text):
        super().__init__()
        self.text = text
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return LLMResponse(text=self.text, provider=self.name, model="stub-model")


def client_for(provider, settings=None):
    settings = settings or LLMSettings(model="stub-model")
    app = create_app(AnalysisService(settings, provider=provider))
    app.testing = True
    return app.test_client()


# --- endpoint ----------------------------------------------------------------

def test_insight_endpoint_returns_structured_insight_and_cleans_report():
    provider = StubProvider(json.dumps(INSIGHT))
    resp = client_for(provider).post("/api/safety-insights", json={"report": REPORT})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["insight"]["risk_level"] == "serious"
    assert body["insight"]["concerns"][0]["action"] == "Check the area"
    assert body["text"] is None and body["model"] == "stub-model"
    req = provider.requests[0]
    assert req.json_output is True
    assert "<report>" in req.user_prompt and "<strong>" not in req.user_prompt  # HTML stripped
    assert "Never declare that there is or is not a fire" in req.system_prompt


def test_insight_endpoint_falls_back_to_text():
    resp = client_for(StubProvider("Plain words, no JSON.")).post("/api/safety-insights", json={"report": REPORT})
    body = resp.get_json()
    assert body["insight"] is None and body["text"] == "Plain words, no JSON."


def test_mock_provider_gives_offline_insight():
    app = create_app(AnalysisService(LLMSettings()))
    app.testing = True
    body = app.test_client().post("/api/safety-insights", json={"report": REPORT}).get_json()
    assert body["provider"] == "mock"
    assert body["insight"]["headline"].startswith("Mock insight")


@pytest.mark.parametrize("payload", [{}, {"report": []}, {"report": {}}, {"report": "text"}, [1]])
def test_insight_endpoint_rejects_bad_reports(payload):
    resp = client_for(StubProvider("{}")).post("/api/safety-insights", json=payload)
    assert resp.status_code == 400


def test_insight_endpoint_enforces_size_limit():
    big = {"notes": ["x" * 1_900] * 100}
    resp = client_for(StubProvider("{}"), LLMSettings(max_input_chars=5_000)).post("/api/safety-insights", json={"report": big})
    assert resp.status_code == 400
    assert "limit" in resp.get_json()["error"]


@pytest.mark.parametrize("retryable, status", [(True, 503), (False, 502)])
def test_insight_endpoint_provider_errors(retryable, status):
    class Failing(LLMProvider):
        name = "failing"

        def generate(self, request):
            raise LLMProviderError("upstream failed", retryable=retryable)

    resp = client_for(Failing()).post("/api/safety-insights", json={"report": REPORT})
    assert resp.status_code == status and resp.get_json()["retryable"] is retryable


# --- parsing ------------------------------------------------------------------

def test_parse_insight_handles_fences_and_bad_levels():
    text = "```json\n" + json.dumps({**INSIGHT, "risk_level": "extreme", "concerns": [{"title": "X", "level": "boom"}]}) + "\n```"
    parsed = parse_insight(text)
    assert parsed["risk_level"] == "unknown"
    assert parsed["concerns"][0]["level"] == "info"
    assert parse_insight("not json") is None
    assert parse_insight("{}") is None


# --- OpenRouter provider ------------------------------------------------------

class FakeReply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def make_provider(reply=None, error=None, **kwargs):
    calls = []

    def opener(req, timeout):
        calls.append((req, timeout))
        if error:
            raise error
        return FakeReply(json.dumps(reply).encode())

    options = {"api_key": "sk-or-test", "model": "dots-studio/dots-3-note-preview:free", **kwargs}
    return OpenRouterProvider(opener=opener, **options), calls


REQUEST = LLMRequest(system_prompt="sys", user_prompt="user", max_output_tokens=500, timeout_seconds=30, json_output=True, temperature=0.2)


def test_openrouter_sends_chat_completion_and_reads_answer():
    provider, calls = make_provider({
        "model": "dots-studio/dots-3-note-preview:free",
        "choices": [{"message": {"content": "answer", "reasoning": "thinking..."}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 34},
    })
    response = provider.generate(REQUEST)
    assert response.text == "answer"
    assert response.usage == {"input_tokens": 12, "output_tokens": 34}
    req, timeout = calls[0]
    assert req.full_url == "https://openrouter.ai/api/v1/chat/completions"
    assert req.get_header("Authorization") == "Bearer sk-or-test"
    assert timeout == 30
    sent = json.loads(req.data)
    assert sent["model"] == "dots-studio/dots-3-note-preview:free"
    assert sent["messages"][0] == {"role": "system", "content": "sys"}
    assert sent["response_format"] == {"type": "json_object"}
    assert sent["max_tokens"] == 500 and sent["temperature"] == 0.2


def test_openrouter_requires_key_and_model():
    with pytest.raises(LLMProviderError, match="LLM_API_KEY"):
        OpenRouterProvider(model="m").generate(REQUEST)
    with pytest.raises(LLMProviderError, match="LLM_MODEL"):
        OpenRouterProvider(api_key="k").generate(LLMRequest(system_prompt="s", user_prompt="u"))


@pytest.mark.parametrize("code, retryable, fragment", [(401, False, "API key"), (404, False, "LLM_MODEL"), (429, True, "rate limit"), (502, True, "HTTP 502")])
def test_openrouter_http_errors(code, retryable, fragment):
    body = io.BytesIO(json.dumps({"error": {"message": "upstream says no"}}).encode())
    err = urllib.error.HTTPError("https://openrouter.ai", code, "err", {}, body)
    provider, _ = make_provider(error=err)
    with pytest.raises(LLMProviderError) as exc:
        provider.generate(REQUEST)
    assert exc.value.retryable is retryable
    assert fragment in str(exc.value) and "upstream says no" in str(exc.value)
    assert "sk-or-test" not in str(exc.value)


def test_openrouter_network_error_is_retryable():
    provider, _ = make_provider(error=urllib.error.URLError("no route"))
    with pytest.raises(LLMProviderError) as exc:
        provider.generate(REQUEST)
    assert exc.value.retryable


def test_openrouter_empty_answer_after_reasoning_asks_for_more_tokens():
    provider, _ = make_provider({"choices": [{"message": {"content": "", "reasoning": "long thoughts"}, "finish_reason": "length"}]})
    with pytest.raises(LLMProviderError, match="LLM_MAX_OUTPUT_TOKENS") as exc:
        provider.generate(REQUEST)
    assert exc.value.retryable is False


def test_openrouter_error_inside_200_response():
    provider, _ = make_provider({"error": {"message": "provider overloaded"}})
    with pytest.raises(LLMProviderError, match="provider overloaded"):
        provider.generate(REQUEST)
