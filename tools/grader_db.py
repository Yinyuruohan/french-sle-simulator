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


# ── Task 4: get_review and save_review ───────────────────────────────────────

def _snapshot_context(conn: sqlite3.Connection, context_id: str) -> str | None:
    """
    Read context from contexts table and return a JSON snapshot string.

    Returns JSON string of {context_id, type, passage, questions, grammar_topics, status}
    or None if context not found.
    """
    row = conn.execute(
        "SELECT context_id, type, passage, questions_json, grammar_topics, status "
        "FROM contexts WHERE context_id = ?",
        (context_id,),
    ).fetchone()

    if row is None:
        return None

    snapshot = {
        "context_id": row["context_id"],
        "type": row["type"],
        "passage": row["passage"],
        "questions": json.loads(row["questions_json"]),
        "grammar_topics": row["grammar_topics"],
        "status": row["status"],
    }
    return json.dumps(snapshot, ensure_ascii=False)


def get_review(context_id: str) -> dict | None:
    """
    Retrieve a review by context_id.

    Returns dict(row) or None if not found.
    """
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM reviews WHERE context_id = ?", (context_id,)
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None
    return dict(row)


def save_review(context_id: str, expert_rating: str, expert_critique: str | None) -> dict | None:
    """
    Create or update a review for the given context_id.

    If review exists: UPDATE expert_rating, expert_critique, updated_at.
    If review is new: create a snapshot of the context and INSERT.

    Returns {"updated_at": <iso string>} or None if context not found in contexts table.
    """
    now = datetime.now().isoformat()

    conn = _get_conn()
    try:
        existing = conn.execute(
            "SELECT context_id FROM reviews WHERE context_id = ?", (context_id,)
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE reviews
                   SET expert_rating = ?, expert_critique = ?, updated_at = ?
                   WHERE context_id = ?""",
                (expert_rating, expert_critique, now, context_id),
            )
            conn.commit()
            return {"updated_at": now}
        else:
            # New review — create snapshot
            snapshot = _snapshot_context(conn, context_id)
            if snapshot is None:
                return None

            conn.execute(
                """INSERT INTO reviews
                   (context_id, model_output, expert_rating, expert_critique,
                    llm_evaluator_rating, llm_evaluator_critique, agreement,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, NULL, NULL, NULL, ?, ?)""",
                (context_id, snapshot, expert_rating, expert_critique, now, now),
            )
            conn.commit()
            return {"updated_at": now}
    finally:
        conn.close()
