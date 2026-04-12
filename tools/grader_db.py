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
