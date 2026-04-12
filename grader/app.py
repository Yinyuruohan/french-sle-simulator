"""
LLM Grader Flask App

Factory-pattern Flask application that exposes a REST API for reviewing
question bank contexts and submitting expert ratings.
"""

import argparse
import json
import os
import sys

# Make tools/ importable when running grader/app.py directly
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, jsonify, request, send_from_directory

from tools.grader_db import (
    cleanup_empty_reviews,
    get_context_data,
    get_contexts_for_review,
    get_review,
    init_reviews_table,
    is_snapshot_outdated,
    save_review,
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


def create_app():
    """Application factory. Initialises DB tables and registers all routes."""
    app = Flask(__name__, static_folder=None)

    # ── Startup ───────────────────────────────────────────────────────────────
    init_reviews_table()
    cleanup_empty_reviews()

    # ── Static file serving ───────────────────────────────────────────────────

    @app.route("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.route("/<path:filename>")
    def static_files(filename):
        if filename.startswith("api/"):
            return jsonify({"error": "Not found"}), 404
        return send_from_directory(STATIC_DIR, filename)

    # ── GET /api/contexts ─────────────────────────────────────────────────────

    @app.route("/api/contexts", methods=["GET"])
    def list_contexts():
        """Return pageable list of contexts with optional filters."""
        filters = {}
        status = request.args.get("status")
        if status:
            filters["status"] = status
        flagged = request.args.get("flagged")
        if flagged:
            filters["flagged"] = flagged
        reviewed = request.args.get("reviewed")
        if reviewed:
            filters["reviewed"] = reviewed

        result = get_contexts_for_review(filters)
        return jsonify(result)

    # ── GET /api/contexts/<context_id> ────────────────────────────────────────

    @app.route("/api/contexts/<context_id>", methods=["GET"])
    def get_context_detail(context_id):
        """Return full context data plus any existing review."""
        context_data = get_context_data(context_id)
        if context_data is None:
            return jsonify({"error": "Context not found"}), 404

        review_row = get_review(context_id)
        review_data = None
        if review_row is not None:
            # Parse the stored snapshot JSON so the caller gets a structured object
            try:
                model_output = json.loads(review_row["model_output"])
            except (TypeError, ValueError):
                model_output = review_row["model_output"]

            outdated = is_snapshot_outdated(context_id)

            review_data = {
                "model_output": model_output,
                "expert_rating": review_row["expert_rating"],
                "expert_critique": review_row["expert_critique"],
                "llm_evaluator_rating": review_row["llm_evaluator_rating"],
                "llm_evaluator_critique": review_row["llm_evaluator_critique"],
                "agreement": review_row["agreement"],
                "snapshot_outdated": bool(outdated) if outdated is not None else False,
            }

        return jsonify({
            "context_id": context_id,
            "context_data": context_data,
            "review": review_data,
        })

    # ── PUT /api/contexts/<context_id>/review ─────────────────────────────────

    @app.route("/api/contexts/<context_id>/review", methods=["PUT"])
    def put_review(context_id):
        """Create or update an expert review for the given context."""
        body = request.get_json(silent=True) or {}

        expert_rating = body.get("expert_rating")
        if expert_rating not in ("Good", "Bad"):
            return jsonify({"error": "expert_rating must be 'Good' or 'Bad'"}), 400

        expert_critique = body.get("expert_critique", "")

        result = save_review(context_id, expert_rating, expert_critique)
        if result is None:
            return jsonify({"error": "Context not found"}), 404

        return jsonify({"success": True, "updated_at": result["updated_at"]})

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LLM Grader Flask API")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("GRADER_PORT", 5001)),
        help="Port to listen on (default: 5001 or $GRADER_PORT)",
    )
    args = parser.parse_args()
    app = create_app()
    app.run(debug=True, port=args.port)