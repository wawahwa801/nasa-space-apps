"""Public-site protection for the LLM endpoints (llm/guard.py)."""

import pytest

from app import create_app
from llm import AnalysisService, LLMSettings
from llm.guard import GuardSettings, RateLimiter, client_id, origin_allowed

SITE = "https://pyroclast.example"
PUBLIC = GuardSettings(require_origin=True, per_client_per_minute=2, per_client_per_day=3, global_per_minute=100)


def client(guard=PUBLIC):
    return create_app(AnalysisService(LLMSettings()), guard=guard).test_client()


def post(c, path="/api/analyze", origin=SITE, ip="203.0.113.5", host="pyroclast.example"):
    headers = {"X-Real-IP": ip}
    if origin:
        headers["Origin"] = origin
    body = {"data": "notes"} if path == "/api/analyze" else {"report": {"overall": "ok", "flags": []}}
    return c.post(path, json=body, headers=headers, base_url=f"https://{host}")


def test_same_site_request_is_answered():
    resp = post(client())
    assert resp.status_code == 200
    assert "mock" in resp.get_json()["output"]


@pytest.mark.parametrize("path", ["/api/analyze", "/api/safety-insights"])
def test_other_sites_and_missing_origin_are_rejected(path):
    c = client()
    assert post(c, path, origin="https://evil.example").status_code == 403
    assert post(c, path, origin=None).status_code == 403


def test_referer_counts_when_origin_is_absent():
    c = client()
    resp = c.post("/api/analyze", json={"data": "x"}, base_url="https://pyroclast.example",
                  headers={"Referer": f"{SITE}/some/page", "X-Real-IP": "198.51.100.1"})
    assert resp.status_code == 200


def test_listed_custom_domain_is_allowed():
    guard = GuardSettings(require_origin=True, allowed_origins=("https://fires.example",))
    assert post(client(guard), origin="https://fires.example", host="backend.internal").status_code == 200


def test_per_client_minute_limit_returns_429_with_retry_after():
    c = client()
    assert post(c).status_code == 200
    assert post(c).status_code == 200
    resp = post(c)
    assert resp.status_code == 429
    assert int(resp.headers["Retry-After"]) >= 1
    assert resp.get_json()["retryable"] is True
    assert post(c, ip="203.0.113.9").status_code == 200  # other visitors unaffected


def test_day_and_global_limits():
    now = [0.0]
    lim = RateLimiter(GuardSettings(per_client_per_minute=0, per_client_per_day=2, global_per_minute=3), clock=lambda: now[0])
    assert lim.check("a") is None and lim.check("a") is None
    assert lim.check("a") > 0  # day limit for "a"
    now[0] += 61
    assert lim.check("b") is None and lim.check("c") is None and lim.check("d") is None
    assert lim.check("e") > 0  # global per-minute cap


def test_local_development_is_unrestricted_by_default(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    for name in ("LLM_REQUIRE_ORIGIN", "LLM_RATE_LIMIT_PER_MINUTE", "LLM_RATE_LIMIT_PER_DAY", "LLM_GLOBAL_LIMIT_PER_MINUTE", "LLM_ALLOWED_ORIGINS"):
        monkeypatch.delenv(name, raising=False)
    g = GuardSettings.from_env()
    assert not g.active
    assert origin_allowed(g, None, None, "localhost:5000")


def test_public_defaults_on_vercel(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("LLM_ALLOWED_ORIGINS", "https://Fires.Example/, ,bad")
    g = GuardSettings.from_env()
    assert g.require_origin and g.per_client_per_minute == 6 and g.per_client_per_day == 100 and g.global_per_minute == 30
    assert g.allowed_origins == ("https://fires.example",)
    assert not origin_allowed(g, "http://localhost:3000", None, "pyroclast.example")


def test_status_reports_configuration_without_the_key():
    settings = LLMSettings(provider="mock", api_key="sk-or-secret-value")
    body = create_app(AnalysisService(settings), guard=PUBLIC).test_client().get("/api/llm/status").get_json()
    assert body["configured"] is False  # mock provider never counts as configured
    assert body["protection"] == {"origin_check": True, "per_client_per_minute": 2, "per_client_per_day": 3, "global_per_minute": 100}
    assert "sk-or-secret-value" not in str(body)


def test_client_id_prefers_platform_headers():
    assert client_id({"X-Real-IP": "1.1.1.1", "X-Forwarded-For": "2.2.2.2"}, "3.3.3.3") == "1.1.1.1"
    assert client_id({"X-Forwarded-For": "2.2.2.2, 10.0.0.1"}, "3.3.3.3") == "2.2.2.2"
    assert client_id({}, "3.3.3.3") == "3.3.3.3"
