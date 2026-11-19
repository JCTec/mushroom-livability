"""Web layer: a deliberately tiny Flask app.

It serves one static page and one JSON document. All analysis happens in
the pipeline; the server only reads the results file, so it can be
restarted or replaced without touching any logic.
"""

from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, send_from_directory

from src.reporting.store import load_results

APP_DIR = Path(__file__).resolve().parent


def create_app(results_path: Path) -> Flask:
    app = Flask(__name__, static_folder=str(APP_DIR / "static"), static_url_path="/static")
    results_path = Path(results_path)

    @app.get("/")
    def index():
        return send_from_directory(APP_DIR / "templates", "index.html")

    @app.get("/api/results")
    def results():
        data = load_results(results_path)
        if data is None:
            return jsonify({"error": "no_results",
                            "message": "No results yet. Run `python main.py pipeline` first."}), 404
        return jsonify(data)

    @app.get("/healthz")
    def health():
        return jsonify({"status": "ok", "results_available": results_path.exists()})

    @app.after_request
    def no_cache(response):
        response.headers["Cache-Control"] = "no-store"
        return response

    return app
