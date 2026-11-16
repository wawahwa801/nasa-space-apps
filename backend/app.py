import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

from database.registry import ModelRegistry, RegistryUnavailable
from hybrid_artifacts import ArtifactUnavailable
from hybrid_service import HybridService, ModelNotReady
from botocore.exceptions import BotoCoreError, ClientError
import zipfile
import pickle

from llm import (
    AnalysisService,
    InputValidationError,
    LLMProviderError,
    LLMSettings,
    SafetyInsightService,
    available_providers,
)

MAX_REQUEST_BYTES = 2 * 1024 * 1024


def create_app(service: AnalysisService | None = None, model_registry=None, hybrid_service=None) -> Flask:
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

    registry = model_registry if model_registry is not None else ModelRegistry({
        "host": os.getenv("DB_HOST"),
        "port": os.getenv("DB_PORT", "5432"),
        "dbname": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        **({"sslmode": os.environ["DB_SSLMODE"]} if os.getenv("DB_SSLMODE") else {}),
        **({"sslrootcert": os.environ["DB_SSLROOTCERT"]} if os.getenv("DB_SSLROOTCERT") else {}),
    })

    hybrid = hybrid_service if hybrid_service is not None else HybridService(registry)

    def hybrid_request(action):
        raw_id = request.headers.get("X-Model-ID")
        if raw_id is not None and (len(raw_id) > 19 or not raw_id.isascii() or not raw_id.isdigit() or not 0 < int(raw_id) < 2**63):
            return jsonify(error="Invalid model version identifier."), 400
        try:
            data, status = hybrid.handle(action, request.method, list(request.args.items(multi=True)),
                                         request.get_json(silent=True) if request.method == "POST" else None,
                                         int(raw_id) if raw_id is not None else None)
        except ModelNotReady:
            return jsonify(error="No ready hybrid model is available for this version. Reload after publishing a verified hybrid package."), 503
        except (RegistryUnavailable, ArtifactUnavailable, BotoCoreError, ClientError, OSError, ValueError, KeyError, ImportError, RuntimeError, EOFError, pickle.UnpicklingError, zipfile.BadZipFile) as error:
            app.logger.warning("Hybrid model unavailable (%s)", type(error).__name__)
            return jsonify(error="Hybrid model could not be loaded. Check server database, S3 permissions and package configuration."), 503
        response = jsonify(data)
        response.headers["Cache-Control"] = "no-store"
        return response, status

    for action, methods in (("runs", ["GET"]), ("compare", ["GET"]), ("simulate", ["POST"]), ("environment", ["GET"])):
        app.add_url_rule("/api/hybrid/" + action, endpoint="hybrid_" + action,
                         view_func=lambda action=action: hybrid_request(action), methods=methods)

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
