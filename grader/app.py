"""
LLM Grader — Flask Application

REST API for expert review of AI-generated exam content.
Serves static SPA files and API endpoints under /api/*.
"""

import argparse
import json
import os
import sys

from flask import Flask, jsonify, request, send_from_directory

# Ensure tools/ is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tools.grader_db import (
    init_reviews_table,
    cleanup_empty_reviews,
    get_contexts_for_review,
)


def create_app() -> Flask:
    """Flask application factory."""
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app = Flask(__name__, static_folder=static_dir)

    # Initialize database on startup
    init_reviews_table()
    cleanup_empty_reviews()

    # ── Static SPA serving ────────────────────────────────────────────────

    @app.route("/")
    def index():
        return send_from_directory(static_dir, "index.html")

    @app.route("/<path:filename>")
    def static_files(filename):
        return send_from_directory(static_dir, filename)

    # ── API: List contexts ────────────────────────────────────────────────

    @app.get("/api/contexts")
    def api_list_contexts():
        filters = {}
        for key in ("status", "flagged", "reviewed"):
            val = request.args.get(key)
            if val is not None:
                filters[key] = val
        return jsonify(get_contexts_for_review(filters))

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LLM Grader server")
    parser.add_argument("--port", type=int, default=int(os.environ.get("GRADER_PORT", 5001)))
    args = parser.parse_args()

    app = create_app()
    app.run(port=args.port, debug=True)