import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

from database.registry import ModelRegistry, RegistryUnavailable

from llm import (
    AnalysisService,
    InputValidationError,
    LLMProviderError,
    LLMSettings,
    SafetyInsightService,
    available_providers,
)

MAX_REQUEST_BYTES = 2 * 1024 * 1024


def create_app(service: AnalysisService | None = None, model_registry=None) -> Flask:
    load_dotenv(Path(__file__).with_name(".env"))
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES
    CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}})

    analysis = service or AnalysisService(LLMSettings.from_env())
    # Shares the configured provider (LLM_PROVIDER / LLM_MODEL / LLM_API_KEY).
    insights = SafetyInsightService(analysis.settings, analysis.provider)

    @app.get("/api/health")
    def health():
        return jsonify(status="Connected", service="project-api")

    registry = model_registry if model_registry is not None else ModelRegistry(os.getenv("DATABASE_URL"))

    @app.get("/api/models/latest")
    def latest_model():
        if set(request.args) - {"model_name"} or len(request.args.getlist("model_name")) > 1:
            return jsonify(error="Supply only one model_name parameter."), 400
        name = request.args.get("model_name", "flex2").strip()
        if not name or len(name) > 100 or "\x00" in name:
            return jsonify(error="model_name must contain 1–100 characters."), 400
        try:
            model = registry.latest(name)
        except RegistryUnavailable:
            return jsonify(error="Model registry is unavailable. Check backend database configuration."), 503
        if model is None:
            return jsonify(error="No ready model found.", model_name=name), 404
        response = jsonify(model=model)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/llm/status")
    def llm_status():
        return jsonify(
            provider=analysis.provider.name,
            model=analysis.settings.model,
            available_providers=available_providers(),
        )

    @app.post("/api/analyze")
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
