# tests/test_grader_db.py
"""Tests for tools/grader_db.py"""
import json
import sqlite3
import uuid
from datetime import datetime

import pytest


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db_path(tmp_path):
    """Provide a temporary database path and patch DB_PATH in both modules."""
    path = str(tmp_path / "test_grader.db")
    import tools.question_bank as qb
    import tools.grader_db as gdb
    qb.DB_PATH = path
    gdb.DB_PATH = path
    yield path


# ── Helpers ───────────────────────────────────────────────────────────────────

def _seed_contexts(db_path: str, count: int) -> list[str]:
    """
    Call init_db() and insert `count` test contexts into the contexts table.
    Returns a list of context_id strings for the inserted rows.
    """
    from tools.question_bank import init_db
    init_db()

    now = datetime.now().isoformat()
    questions = [
        {
            "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
            "correct_answer": "A",
            "grammar_topic": "agreement",
            "explanation": {"why_correct": "Reason", "grammar_rule": "Rule"},
        }
    ]
    questions_json = json.dumps(questions, ensure_ascii=False)

    context_ids = []
    conn = sqlite3.connect(db_path)
    try:
        for i in range(count):
            cid = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO contexts
                   (context_id, type, passage, questions_json, num_questions,
                    grammar_topics, status, source_session, created_at,
                    times_served, passage_hash, last_incorrect, user_flags)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    cid,
                    "fill_in_blank",
                    f"Test passage {i} with (1) _______________ blank.",
                    questions_json,
                    1,
                    "agreement",
                    "reviewed",
                    "test_session",
                    now,
                    0,
                    f"hash_{i}_{cid}",
                    0,
                    0,
                ),
            )
            context_ids.append(cid)
        conn.commit()
    finally:
        conn.close()

    return context_ids


# ── Task 2: init_reviews_table and cleanup_empty_reviews ─────────────────────

def test_init_reviews_table_creates_table(db_path):
    """init_reviews_table creates the reviews table with expected columns."""
    from tools.grader_db import init_reviews_table
    _seed_contexts(db_path, 0)  # ensure DB file exists via init_db
    init_reviews_table()

    conn = sqlite3.connect(db_path)
    cursor = conn.execute("PRAGMA table_info(reviews)")
    columns = {row[1] for row in cursor.fetchall()}
    conn.close()

    expected = {
        "context_id", "model_output", "expert_rating", "expert_critique",
        "llm_evaluator_rating", "llm_evaluator_critique", "agreement",
        "created_at", "updated_at",
    }
    assert expected == columns


def test_init_reviews_table_is_idempotent(db_path):
    """Calling init_reviews_table twice does not raise."""
    from tools.grader_db import init_reviews_table
    _seed_contexts(db_path, 0)
    init_reviews_table()
    init_reviews_table()  # should not raise


def test_cleanup_empty_reviews_deletes_unrated(db_path):
    """cleanup_empty_reviews deletes rows where expert_rating IS NULL."""
    from tools.grader_db import init_reviews_table, cleanup_empty_reviews

    context_ids = _seed_contexts(db_path, 3)
    init_reviews_table()

    now = datetime.now().isoformat()
    conn = sqlite3.connect(db_path)
    # Insert 2 unrated reviews and 1 rated review
    for cid in context_ids[:2]:
        conn.execute(
            """INSERT INTO reviews (context_id, model_output, expert_rating, expert_critique,
               llm_evaluator_rating, llm_evaluator_critique, agreement, created_at, updated_at)
               VALUES (?, ?, NULL, NULL, NULL, NULL, NULL, ?, ?)""",
            (cid, "{}", now, now),
        )
    conn.execute(
        """INSERT INTO reviews (context_id, model_output, expert_rating, expert_critique,
           llm_evaluator_rating, llm_evaluator_critique, agreement, created_at, updated_at)
           VALUES (?, ?, ?, NULL, NULL, NULL, NULL, ?, ?)""",
        (context_ids[2], "{}", "good", now, now),
    )
    conn.commit()
    conn.close()

    deleted = cleanup_empty_reviews()
    assert deleted == 2

    conn = sqlite3.connect(db_path)
    remaining = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    conn.close()
    assert remaining == 1
