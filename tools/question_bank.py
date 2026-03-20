"""
SLE Question Bank

Caches validated exam contexts in a local SQLite database for instant
exam assembly. Contexts are stored after passing quality review and
upgraded with explanations after the full exam cycle completes.
"""

import hashlib
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "question_bank.db")


def _get_conn() -> sqlite3.Connection:
    """Get a SQLite connection to the question bank database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the question bank database and table if they don't exist."""
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contexts (
                context_id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                passage TEXT NOT NULL,
                questions_json TEXT NOT NULL,
                num_questions INTEGER NOT NULL,
                grammar_topics TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'reviewed',
                source_session TEXT NOT NULL,
                created_at TEXT NOT NULL,
                times_served INTEGER NOT NULL DEFAULT 0,
                passage_hash TEXT NOT NULL,
                last_incorrect INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()
    finally:
        conn.close()
