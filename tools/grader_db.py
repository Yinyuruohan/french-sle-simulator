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
    """Delete reviews where both expert_rating and llm_evaluator_rating are NULL. Returns the number of rows deleted."""
    conn = _get_conn()
    try:
        cursor = conn.execute(
            "DELETE FROM reviews WHERE expert_rating IS NULL AND llm_evaluator_rating IS NULL"
        )
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
        SELECT c.context_id, c.type, c.status, c.user_flags, r.expert_rating, r.llm_evaluator_rating
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
            "type": row["type"],
            "status": row["status"],
            "user_flags": row["user_flags"],
            "expert_rating": row["expert_rating"],
            "llm_evaluator_rating": row["llm_evaluator_rating"],
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
    Raises ValueError if expert_rating is not 'Good' or 'Bad'.
    """
    if expert_rating not in ("Good", "Bad"):
        raise ValueError(f"expert_rating must be 'Good' or 'Bad', got {expert_rating!r}")

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


def save_llm_review(
    context_id: str, llm_rating: str, llm_critique: str
) -> dict | None:
    """
    Create or update the LLM evaluator fields for the given context_id.

    If a review row exists: UPDATE llm_evaluator_rating, llm_evaluator_critique, updated_at only.
    If no row exists: INSERT a new row with a context snapshot; expert_rating and agreement left NULL.

    Returns {"updated_at": <iso string>} or None if context_id not in contexts table.
    """
    if llm_rating not in ("Good", "Bad"):
        raise ValueError(f"llm_rating must be 'Good' or 'Bad', got {llm_rating!r}")

    now = datetime.now().isoformat()

    conn = _get_conn()
    try:
        existing = conn.execute(
            "SELECT context_id FROM reviews WHERE context_id = ?", (context_id,)
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE reviews
                   SET llm_evaluator_rating = ?, llm_evaluator_critique = ?, updated_at = ?
                   WHERE context_id = ?""",
                (llm_rating, llm_critique, now, context_id),
            )
            conn.commit()
            return {"updated_at": now}
        else:
            snapshot = _snapshot_context(conn, context_id)
            if snapshot is None:
                return None

            conn.execute(
                """INSERT INTO reviews
                   (context_id, model_output, expert_rating, expert_critique,
                    llm_evaluator_rating, llm_evaluator_critique, agreement,
                    created_at, updated_at)
                   VALUES (?, ?, NULL, NULL, ?, ?, NULL, ?, ?)""",
                (context_id, snapshot, llm_rating, llm_critique, now, now),
            )
            conn.commit()
            return {"updated_at": now}
    finally:
        conn.close()


# ── Task 5: snapshot staleness detection ─────────────────────────────────────

def _context_data_hash(context_data: dict) -> str:
    """
    Compute SHA-256 hash of context data for staleness comparison.

    Hashes {passage, questions, grammar_topics} with sorted keys.
    """
    subset = {
        "passage": context_data["passage"],
        "questions": context_data["questions"],
        "grammar_topics": context_data["grammar_topics"],
    }
    canonical = json.dumps(subset, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def is_snapshot_outdated(context_id: str) -> bool | None:
    """
    Compare snapshot hash to current context hash.

    Returns:
        False — snapshot matches current context (up to date)
        True  — snapshot differs from current context (outdated)
        None  — no review exists, or context has been deleted
    """
    conn = _get_conn()
    try:
        review_row = conn.execute(
            "SELECT model_output FROM reviews WHERE context_id = ?", (context_id,)
        ).fetchone()

        if review_row is None:
            return None

        context_row = conn.execute(
            "SELECT passage, questions_json, grammar_topics FROM contexts WHERE context_id = ?",
            (context_id,),
        ).fetchone()

        if context_row is None:
            return None

        # Materialize row data before closing the connection
        snapshot_json = review_row["model_output"]
        current_passage = context_row["passage"]
        current_questions_json = context_row["questions_json"]
        current_grammar_topics = context_row["grammar_topics"]
    finally:
        conn.close()

    # Parse snapshot from stored model_output JSON
    snapshot = json.loads(snapshot_json)
    snapshot_hash = _context_data_hash({
        "passage": snapshot["passage"],
        "questions": snapshot["questions"],
        "grammar_topics": snapshot["grammar_topics"],
    })

    # Compute current context hash
    current_data = {
        "passage": current_passage,
        "questions": json.loads(current_questions_json),
        "grammar_topics": current_grammar_topics,
    }
    current_hash = _context_data_hash(current_data)

    return snapshot_hash != current_hash


def get_context_data(context_id: str) -> dict | None:
    """
    Read live context data from contexts table.

    Returns dict with context fields or None if not found.
    """
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT context_id, type, passage, questions_json, grammar_topics, status "
            "FROM contexts WHERE context_id = ?",
            (context_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    return {
        "context_id": row["context_id"],
        "type": row["type"],
        "passage": row["passage"],
        "questions": json.loads(row["questions_json"]),
        "grammar_topics": row["grammar_topics"],
        "status": row["status"],
    }
