"""
LLM Grader — Reviews Data Layer

Manages the `reviews` table in the shared question_bank.db.
Read-only access to the `contexts` table for snapshots and filtering.
Never writes to the `contexts` table.
"""

import hashlib
import json
import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "question_bank.db")


def _get_conn() -> sqlite3.Connection:
    """Get a SQLite connection to the question bank database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── Task 2: init_reviews_table and cleanup_empty_reviews ─────────────────────

def init_reviews_table():
    """Create the reviews table if it doesn't exist."""
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                context_id TEXT PRIMARY KEY,
                model_output TEXT NOT NULL,
                expert_rating TEXT,
                expert_critique TEXT,
                llm_evaluator_rating TEXT,
                llm_evaluator_critique TEXT,
                agreement INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()


def cleanup_empty_reviews() -> int:
    """Delete reviews where expert_rating is NULL. Returns the number of rows deleted."""
    conn = _get_conn()
    try:
        cursor = conn.execute("DELETE FROM reviews WHERE expert_rating IS NULL")
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


# ── Task 3: get_contexts_for_review ──────────────────────────────────────────

def get_contexts_for_review(filters: dict) -> dict:
    """
    Return contexts for review with optional filters.

    Args:
        filters: dict with optional keys:
            - status: exact match on c.status
            - flagged: "true" = user_flags >= 1, "false" = user_flags == 0
            - reviewed: "true" = expert_rating IS NOT NULL, "false" = context_id IS NULL in reviews

    Returns:
        {"total": int, "items": [{"context_id", "status", "user_flags", "expert_rating"}, ...]}
    """
    conditions = []
    params = []

    status = filters.get("status")
    if status:
        conditions.append("c.status = ?")
        params.append(status)

    flagged = filters.get("flagged")
    if flagged == "true":
        conditions.append("c.user_flags >= 1")
    elif flagged == "false":
        conditions.append("c.user_flags = 0")

    reviewed = filters.get("reviewed")
    if reviewed == "true":
        conditions.append("r.expert_rating IS NOT NULL")
    elif reviewed == "false":
        conditions.append("r.context_id IS NULL")

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    query = f"""
        SELECT c.context_id, c.status, c.user_flags, r.expert_rating
        FROM contexts c
        LEFT JOIN reviews r ON c.context_id = r.context_id
        {where_clause}
        ORDER BY c.created_at DESC
    """

    conn = _get_conn()
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    items = [
        {
            "context_id": row["context_id"],
            "status": row["status"],
            "user_flags": row["user_flags"],
            "expert_rating": row["expert_rating"],
        }
        for row in rows
    ]

    return {"total": len(items), "items": items}


# ── Task 4 stub (placeholder for commit boundary) ────────────────────────────

def save_review(context_id: str, expert_rating: str, expert_critique) -> dict | None:
    """Stub — implemented in Task 4."""
    raise NotImplementedError("save_review is implemented in Task 4")
