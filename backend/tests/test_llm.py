import pytest

from app import create_app
from llm import (
    AnalysisService,
    InputValidationError,
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    LLMSettings,
    process_input,
)


class RecordingProvider(LLMProvider):
    name = "recording"

    def __init__(self):
        super().__init__()
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return LLMResponse(text="ok", provider=self.name, model="test-model")


class FailingProvider(LLMProvider):
    name = "failing"

    def __init__(self, retryable):
        super().__init__()
        self.retryable = retryable

    def generate(self, request):
        raise LLMProviderError("upstream failed", retryable=self.retryable)


def make_client(provider=None, settings=None):
    settings = settings or LLMSettings()
    service = AnalysisService(settings, provider=provider)
    app = create_app(service)
    app.testing = True
    return app.test_client()


# --- input processing -------------------------------------------------------

def test_series_stats():
    result = process_input([1, 2, 3, 4])
    assert result.data_type == "quantitative"
    assert result.shape == "series"
    stats = result.summary["series"]
    assert stats["mean"] == 2.5
    assert stats["median"] == 2.5
    assert stats["min"] == 1 and stats["max"] == 4


def test_records_mixed_columns():
    rows = [{"site": "A", "temp": 20}, {"site": "B", "temp": 24}, {"site": "A"}]
    result = process_input(rows)
    cols = result.summary["columns"]
    assert result.shape == "records"
    assert cols["temp"]["kind"] == "numeric"
    assert cols["temp"]["missing"] == 1
    assert cols["site"]["kind"] == "categorical"
    assert cols["site"]["top_values"][0] == {"value": "A", "count": 2}


def test_named_series():
    result = process_input({"a": [1, 2], "b": [3, 5]})
    assert result.shape == "named_series"
    assert result.summary["columns"]["b"]["mean"] == 4


def test_qualitative_text_and_list():
    assert process_input("smoke seen near ridge").data_type == "qualitative"
    listed = process_input(["first", "second"])
    assert listed.shape == "text_list"
    assert "1. first" in listed.data_text


@pytest.mark.parametrize("bad", [None, "", [], {}, [1, "a"], [True, False], 5])
def test_rejects_bad_data(bad):
    with pytest.raises(InputValidationError):
        process_input(bad)


def test_rejects_mismatched_type_and_oversize():
    with pytest.raises(InputValidationError):
        process_input([1, 2], "qualitative")
    with pytest.raises(InputValidationError):
        process_input("x" * 101, max_chars=100)


# --- API --------------------------------------------------------------------

def test_analyze_endpoint_builds_prompt():
    provider = RecordingProvider()
    client = make_client(provider, LLMSettings(model="test-model", max_output_tokens=50))
    resp = client.post(
        "/api/analyze",
        json={"data": [1, 2, 3], "instructions": "Find the trend.", "context": "Daily readings"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["output"] == "ok"
    assert body["input"]["data_type"] == "quantitative"

    sent = provider.requests[0]
    assert "Find the trend." in sent.user_prompt
    assert "Daily readings" in sent.user_prompt
    assert "<data>\n[1, 2, 3]\n</data>" in sent.user_prompt
    assert sent.max_output_tokens == 50


def test_analyze_default_mock_provider():
    client = make_client()
    resp = client.post("/api/analyze", json={"data": "Some field notes."})
    assert resp.status_code == 200
    assert resp.get_json()["provider"] == "mock"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"data": "not json", "content_type": "text/plain"},
        {"json": ["not", "an", "object"]},
        {"json": {"data": "x", "instructions": 5}},
        {"json": {"data": "x", "data_type": "numbers"}},
    ],
)
def test_analyze_bad_requests(kwargs):
    resp = make_client().post("/api/analyze", **kwargs)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


@pytest.mark.parametrize("retryable,status", [(True, 503), (False, 502)])
def test_provider_errors(retryable, status):
    client = make_client(FailingProvider(retryable))
    resp = client.post("/api/analyze", json={"data": "text"})
    assert resp.status_code == status
    assert resp.get_json() == {"error": "upstream failed", "retryable": retryable}


def test_unknown_provider_fails_at_startup():
    with pytest.raises(LLMProviderError):
        AnalysisService(LLMSettings(provider="does-not-exist"))


def test_status_and_health():
    client = make_client(RecordingProvider())
    assert client.get("/api/health").get_json()["status"] == "Connected"
    status = client.get("/api/llm/status").get_json()
    assert status["provider"] == "recording"
    assert "mock" in status["available_providers"]


# Regression tests for the PR #6 review findings.


@pytest.mark.parametrize(
    "body",
    [
        '{"data": [1e308, 1e308]}',  # finite inputs whose sum overflows
        '{"data": [' + "1" + "0" * 400 + "]}",  # integer too large for a float
        '{"data": {"a": [1e308, 1e308]}}',
        '{"data": [{"a": 1e308}, {"a": 1e308}]}',
        '{"data": [{"a": ' + "1" + "0" * 400 + '}, {"a": 2}]}',
    ],
)
def test_out_of_range_numbers_return_400(body):
    resp = make_client().post("/api/analyze", data=body, content_type="application/json")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_size_limit_checked_before_summaries(monkeypatch):
    import llm.input_processing as ip

    def fail(*_args, **_kwargs):
        raise AssertionError("summary computed for oversize data")

    monkeypatch.setattr(ip, "_summarize_series", fail)
    monkeypatch.setattr(ip, "_summarize_records", fail)
    with pytest.raises(InputValidationError, match="character limit"):
        process_input(list(range(1000)), max_chars=100)
    with pytest.raises(InputValidationError, match="character limit"):
        process_input([{"a": i} for i in range(1000)], max_chars=100)


def test_too_many_columns_rejected():
    sparse = [{f"k{i}": i} for i in range(500)]
    with pytest.raises(InputValidationError, match="columns"):
        process_input(sparse)
    with pytest.raises(InputValidationError, match="columns"):
        process_input({f"k{i}": [i] for i in range(500)})


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan"), 10**400])
@pytest.mark.parametrize("records", [False, True])
@pytest.mark.parametrize("prefix", [1, "site A"])
def test_invalid_numbers_in_columns_return_400(value, records, prefix):
    data = [{"a": prefix}, {"a": value}] if records else {"a": [prefix, value]}
    provider = RecordingProvider()
    response = make_client(provider).post("/api/analyze", json={"data": data})
    assert response.status_code == 400
    assert "error" in response.get_json()
    assert not provider.requests
