from functools import wraps

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

from llm import (
    AnalysisService,
    InputValidationError,
    LLMProviderError,
    LLMSettings,
    SafetyInsightService,
    available_providers,
)
from llm.guard import GuardSettings, RateLimiter, client_id, origin_allowed

MAX_REQUEST_BYTES = 2 * 1024 * 1024


def create_app(service: AnalysisService | None = None, guard: GuardSettings | None = None) -> Flask:
    # Secrets come from the environment only: backend/.env locally (gitignored), or the
    # hosting platform's environment settings in production. Never from the browser.
    load_dotenv()
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES
    CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}})

    analysis = service or AnalysisService(LLMSettings.from_env())
    # Shares the configured provider (LLM_PROVIDER / LLM_MODEL / LLM_API_KEY).
    insights = SafetyInsightService(analysis.settings, analysis.provider)
    guard = guard or GuardSettings.from_env()
    limiter = RateLimiter(guard)

    def protected(view):
        """Same-site and rate-limit checks for endpoints that spend the LLM key."""
        @wraps(view)
        def wrapper(*args, **kwargs):
            host = request.headers.get("X-Forwarded-Host") or request.host
            if not origin_allowed(guard, request.headers.get("Origin"), request.headers.get("Referer"), host):
                return jsonify(error="AI insights only answer requests from this site."), 403
            wait = limiter.check(client_id(request.headers, request.remote_addr))
            if wait is not None:
                response = jsonify(error=f"Too many AI insight requests. Try again in {wait} s.", retryable=True)
                response.headers["Retry-After"] = str(wait)
                return response, 429
            return view(*args, **kwargs)
        return wrapper

    @app.get("/api/health")
    def health():
        return jsonify(status="Connected", service="project-api")

    @app.get("/api/llm/status")
    def llm_status():
        # Reports whether a real provider and key are set, never the key itself.
        return jsonify(
            provider=analysis.provider.name,
            model=analysis.settings.model,
            available_providers=available_providers(),
            configured=analysis.provider.name != "mock" and bool(analysis.settings.api_key),
            protection={
                "origin_check": guard.require_origin or bool(guard.allowed_origins),
                "per_client_per_minute": guard.per_client_per_minute,
                "per_client_per_day": guard.per_client_per_day,
                "global_per_minute": guard.global_per_minute,
            },
        )

    @app.post("/api/analyze")
    @protected
    def analyze():
        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify(error="Request body must be valid JSON with Content-Type: application/json."), 400
        try:
            return jsonify(analysis.analyze(payload))
        except InputValidationError as exc:
            return jsonify(error=str(exc)), 400
        except LLMProviderError as exc:
            app.logger.warning("LLM provider error: %s", exc)
            status = 503 if exc.retryable else 502
            return jsonify(error=str(exc), retryable=exc.retryable), status

    @app.post("/api/safety-insights")
    @protected
    def safety_insights():
        """Plain-language insight on the fire dashboard's current safety report."""
        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify(error="Request body must be valid JSON with Content-Type: application/json."), 400
        try:
            return jsonify(insights.explain(payload))
        except InputValidationError as exc:
            return jsonify(error=str(exc)), 400
        except LLMProviderError as exc:
            app.logger.warning("LLM provider error: %s", exc)
            status = 503 if exc.retryable else 502
            return jsonify(error=str(exc), retryable=exc.retryable), status

    @app.errorhandler(413)
    def too_large(_exc):
        return jsonify(error=f"Request body exceeds {MAX_REQUEST_BYTES // (1024 * 1024)} MB."), 413

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=True)
