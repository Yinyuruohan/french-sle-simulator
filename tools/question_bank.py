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


def _passage_hash(passage: str) -> str:
    """SHA-256 hash of normalized passage text for deduplication."""
    normalized = passage.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def cache_contexts(exam_data: dict, status: str = "reviewed"):
    """
    Extract each context from an exam dict and insert into the bank.
    Extracts type from each context dict and collects grammar_topics from
    each question's grammar_topic field. Deduplicates by passage text hash —
    skips if a context with the same passage already exists.
    """
    conn = _get_conn()
    try:
        session_id = exam_data.get("session_id", "unknown")
        now = datetime.now().isoformat()

        for ctx in exam_data.get("contexts", []):
            p_hash = _passage_hash(ctx["passage"])

            # Check for duplicate
            existing = conn.execute(
                "SELECT 1 FROM contexts WHERE passage_hash = ?", (p_hash,)
            ).fetchone()
            if existing:
                continue

            questions = ctx.get("questions", [])
            # Strip question_id from stored questions (reassigned at assembly)
            stored_questions = []
            for q in questions:
                stored_questions.append({
                    "options": q["options"],
                    "correct_answer": q["correct_answer"],
                    "grammar_topic": q["grammar_topic"],
                    "explanation": None,
                })

            topics = ",".join(q["grammar_topic"] for q in questions)

            conn.execute(
                """INSERT INTO contexts
                   (context_id, type, passage, questions_json, num_questions,
                    grammar_topics, status, source_session, created_at,
                    times_served, passage_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                (
                    str(uuid.uuid4()),
                    ctx["type"],
                    ctx["passage"],
                    json.dumps(stored_questions, ensure_ascii=False),
                    len(questions),
                    topics,
                    status,
                    session_id,
                    now,
                    p_hash,
                ),
            )

        conn.commit()
    finally:
        conn.close()


def get_bank_stats() -> dict:
    """Return question bank statistics."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT status, COUNT(*), COALESCE(SUM(num_questions), 0) FROM contexts GROUP BY status"
        ).fetchall()
    finally:
        conn.close()

    stats = {"total_contexts": 0, "total_questions": 0, "reviewed": 0, "battle_tested": 0}
    for row in rows:
        status, count, q_sum = row[0], row[1], row[2]
        stats["total_contexts"] += count
        stats["total_questions"] += q_sum
        if status in ("reviewed", "battle_tested"):
            stats[status] = count

    return stats
