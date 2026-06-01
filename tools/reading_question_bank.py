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


def assemble_exam_from_cache(num_questions: int) -> dict:
    """Pick N contexts with even stem_family spread; renumber ids.

    Ordering: user-flagged deprioritized → battle_tested > reviewed > warned →
    times_served ASC, RANDOM().

    Returns {available_questions: int, exam: dict|None}.
    """
    conn = _get_conn()
    try:
        available = conn.execute("SELECT COUNT(*) FROM rc_contexts").fetchone()[0]
        if available == 0 or num_questions <= 0:
            return {"available_questions": available, "exam": None}

        rows = conn.execute(
            "SELECT context_id, passage, has_signature, question_json, "
            "stem_family, status, user_flags "
            "FROM rc_contexts "
            "ORDER BY "
            "  CASE WHEN user_flags >= 1 THEN 1 ELSE 0 END, "
            "  CASE status WHEN 'battle_tested' THEN 0 WHEN 'reviewed' THEN 1 WHEN 'warned' THEN 2 END, "
            "  times_served ASC, RANDOM()"
        ).fetchall()

        selected = _select_contexts_evenly(rows, num_questions)
        if not selected:
            return {"available_questions": available, "exam": None}

        for row in selected:
            conn.execute(
                "UPDATE rc_contexts SET times_served = times_served + 1 WHERE context_id = ?",
                (row["context_id"],),
            )
        conn.commit()
    finally:
        conn.close()

    exam = _build_exam_from_rows(selected)
    return {"available_questions": available, "exam": exam}


def _select_contexts_evenly(rows, target_questions: int) -> list:
    """Greedy pick by least-represented stem_family, up to target. RC has 1 q per ctx."""
    if not rows or target_questions <= 0:
        return []

    remaining = list(rows)
    family_counts: dict[str, int] = {}
    selected = []
    while remaining and len(selected) < target_questions:
        best = None
        best_score = float("inf")
        for row in remaining:
            score = family_counts.get(row["stem_family"], 0)
            if score < best_score:
                best_score = score
                best = row
        if best is None:
            break
        selected.append(best)
        family_counts[best["stem_family"]] = family_counts.get(best["stem_family"], 0) + 1
        remaining.remove(best)

    return selected


def _build_exam_from_rows(rows: list) -> dict:
    """Return an RC exam dict, renumbering context_ids and question_ids to 1..N."""
    contexts = []
    for idx, row in enumerate(rows, start=1):
        stored_q = json.loads(row["question_json"])
        question = {
            "question_id": idx,
            "stem_family": stored_q["stem_family"],
            "question_text": stored_q["question_text"],
            "options": stored_q["options"],
            "correct_answer": stored_q["correct_answer"],
            "justification": stored_q.get("justification", ""),
            "bolded_term": stored_q.get("bolded_term"),
        }
        contexts.append({
            "context_id": idx,
            "passage": row["passage"],
            "has_signature": bool(row["has_signature"]),
            "questions": [question],
            "bank_context_id": row["context_id"],
            "original_passage_hash": _passage_hash(row["passage"]),
            "bank_status": row["status"],
        })

    timestamp = datetime.now()
    return {
        "session_id": f"reading_{timestamp.strftime('%Y%m%d_%H%M%S')}",
        "timestamp": timestamp.isoformat(),
        "exam_kind": "reading_comprehension",
        "num_questions": len(contexts),
        "contexts": contexts,
        "source": "cache",
    }


def flag_context(bank_context_id: str = None, passage_hash: str = None, category: str = ""):
    """Increment user_flags. (Tracking-file logging added in Task 6.)"""
    conn = _get_conn()
    try:
        if bank_context_id:
            conn.execute(
                "UPDATE rc_contexts SET user_flags = user_flags + 1 WHERE context_id = ?",
                (bank_context_id,),
            )
        elif passage_hash:
            conn.execute(
                "UPDATE rc_contexts SET user_flags = user_flags + 1 WHERE passage_hash = ?",
                (passage_hash,),
            )
        conn.commit()
    finally:
        conn.close()
