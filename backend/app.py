from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

from llm import (
    AnalysisService,
    InputValidationError,
    LLMProviderError,
    LLMSettings,
    available_providers,
)

MAX_REQUEST_BYTES = 2 * 1024 * 1024


def create_app(service: AnalysisService | None = None) -> Flask:
    load_dotenv()
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES
    CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}})

    analysis = service or AnalysisService(LLMSettings.from_env())

    @app.get("/api/health")
    def health():
        return jsonify(status="Connected", service="project-api")

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

    @app.errorhandler(413)
    def too_large(_exc):
        return jsonify(error=f"Request body exceeds {MAX_REQUEST_BYTES // (1024 * 1024)} MB."), 413

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=True)
