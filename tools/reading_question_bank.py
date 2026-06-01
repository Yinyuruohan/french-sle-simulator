"""
SLE Reading Comprehension Question Bank.

Caches validated RC contexts in a local SQLite database so future exams
can be assembled instantly with no API call. Mirrors tools/question_bank.py
but with the RC schema (1 question per context, stem_family, has_signature,
single question_json dict).
"""
import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                       "reading_question_bank.db")
SYSTEM_TRACKING_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                    "system_error_tracking.md")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create rc_contexts if it doesn't exist. Drop+recreate old schemas."""
    conn = _get_conn()
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='rc_contexts'"
        )
        if cursor.fetchone():
            cols = {r[1] for r in conn.execute("PRAGMA table_info(rc_contexts)").fetchall()}
            if "user_flags" not in cols:
                conn.execute("DROP TABLE rc_contexts")
                conn.commit()

        conn.execute("""
            CREATE TABLE IF NOT EXISTS rc_contexts (
                context_id TEXT PRIMARY KEY,
                passage TEXT NOT NULL,
                has_signature INTEGER NOT NULL DEFAULT 0,
                question_json TEXT NOT NULL,
                stem_family TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'reviewed',
                source_session TEXT NOT NULL,
                created_at TEXT NOT NULL,
                times_served INTEGER NOT NULL DEFAULT 0,
                passage_hash TEXT NOT NULL UNIQUE,
                last_incorrect INTEGER NOT NULL DEFAULT 0,
                user_flags INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()
    finally:
        conn.close()


def _passage_hash(passage: str) -> str:
    normalized = passage.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def cache_contexts(exam: dict, status: str = "reviewed"):
    """Insert each context from an exam dict. Dedup by passage_hash."""
    conn = _get_conn()
    try:
        session_id = exam.get("session_id", "unknown")
        now = datetime.now().isoformat()

        for ctx in exam.get("contexts", []):
            p_hash = _passage_hash(ctx["passage"])
            existing = conn.execute(
                "SELECT 1 FROM rc_contexts WHERE passage_hash = ?", (p_hash,)
            ).fetchone()
            if existing:
                continue

            q = ctx["questions"][0]
            stored_q = {
                "stem_family": q["stem_family"],
                "question_text": q["question_text"],
                "options": q["options"],
                "correct_answer": q["correct_answer"],
                "justification": q.get("justification", ""),
                "bolded_term": q.get("bolded_term"),
            }

            conn.execute(
                """INSERT INTO rc_contexts
                   (context_id, passage, has_signature, question_json,
                    stem_family, status, source_session, created_at,
                    times_served, passage_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                (
                    str(uuid.uuid4()),
                    ctx["passage"],
                    1 if ctx.get("has_signature") else 0,
                    json.dumps(stored_q, ensure_ascii=False),
                    q["stem_family"],
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
    """Return cache stats grouped by status. total_questions == total_contexts for RC."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT status, COUNT(*) FROM rc_contexts GROUP BY status"
        ).fetchall()
    finally:
        conn.close()

    stats = {
        "total_contexts": 0, "total_questions": 0,
        "reviewed": 0, "battle_tested": 0, "warned": 0,
        "reviewed_questions": 0, "battle_tested_questions": 0, "warned_questions": 0,
    }
    for row in rows:
        status, count = row[0], row[1]
        stats["total_contexts"] += count
        stats["total_questions"] += count
        if status in ("reviewed", "battle_tested", "warned"):
            stats[status] = count
            stats[f"{status}_questions"] = count
    return stats
