# tests/test_question_bank.py
"""Tests for tools/question_bank.py"""
import json
import os
import sqlite3
import tempfile
import pytest


@pytest.fixture
def db_path(tmp_path):
    """Provide a temporary database path and patch DB_PATH."""
    path = str(tmp_path / "test_question_bank.db")
    import tools.question_bank as qb
    qb.DB_PATH = path
    yield path


def test_init_db_creates_table(db_path):
    """init_db creates the contexts table with expected columns."""
    from tools.question_bank import init_db
    init_db()
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("PRAGMA table_info(contexts)")
    columns = {row[1] for row in cursor.fetchall()}
    conn.close()
    expected = {"context_id", "type", "passage", "questions_json", "num_questions",
                "grammar_topics", "status", "source_session", "created_at",
                "times_served", "passage_hash", "last_incorrect"}
    assert expected == columns


def test_init_db_is_idempotent(db_path):
    """Calling init_db twice does not raise."""
    from tools.question_bank import init_db
    init_db()
    init_db()  # should not raise


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_exam(num_contexts=2):
    """Helper: build a minimal exam dict matching generate_exam() output."""
    contexts = []
    qid = 1
    for i in range(1, num_contexts + 1):
        ctx_type = "fill_in_blank" if i % 2 == 1 else "error_identification"
        questions = []
        num_q = 2 if ctx_type == "fill_in_blank" else 1
        for _ in range(num_q):
            questions.append({
                "question_id": qid,
                "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
                "correct_answer": "A",
                "grammar_topic": "preposition" if qid % 2 == 0 else "agreement",
            })
            qid += 1
        passage = f"Test passage ({i}) _______________ for context {i}."
        contexts.append({
            "context_id": i,
            "type": ctx_type,
            "passage": passage,
            "questions": questions,
        })
    return {
        "session_id": "exam_20260318_120000",
        "timestamp": "2026-03-18T12:00:00",
        "num_questions": qid - 1,
        "contexts": contexts,
    }


# ── Task 2: cache_contexts and get_bank_stats ───────────────────────────────

def test_cache_contexts_inserts_rows(db_path):
    """cache_contexts inserts one row per context."""
    from tools.question_bank import init_db, cache_contexts, get_bank_stats
    init_db()
    exam = _make_exam(2)
    cache_contexts(exam)
    stats = get_bank_stats()
    assert stats["total_contexts"] == 2
    assert stats["total_questions"] == 3  # 2 fill_in_blank + 1 error_id


def test_cache_contexts_deduplicates_by_passage(db_path):
    """Inserting the same exam twice does not create duplicate rows."""
    from tools.question_bank import init_db, cache_contexts, get_bank_stats
    init_db()
    exam = _make_exam(2)
    cache_contexts(exam)
    cache_contexts(exam)  # same passages
    stats = get_bank_stats()
    assert stats["total_contexts"] == 2  # not 4


def test_cache_contexts_stores_correct_status(db_path):
    """Cached contexts default to 'reviewed' status."""
    from tools.question_bank import init_db, cache_contexts, get_bank_stats
    init_db()
    exam = _make_exam(1)
    cache_contexts(exam, status="reviewed")
    stats = get_bank_stats()
    assert stats["reviewed"] == 1
    assert stats["battle_tested"] == 0


# ── Task 3: upgrade_to_battle_tested ────────────────────────────────────────

def test_upgrade_to_battle_tested(db_path):
    """upgrade_to_battle_tested updates status and stores explanations."""
    from tools.question_bank import init_db, cache_contexts, upgrade_to_battle_tested, get_bank_stats
    init_db()
    exam = _make_exam(1)  # 1 fill_in_blank context with 2 questions
    cache_contexts(exam)

    # Build evaluation data matching evaluate_exam() output
    evaluation = {
        "session_id": exam["session_id"],
        "context_results": [
            {
                "context_id": 1,
                "type": "fill_in_blank",
                "passage": exam["contexts"][0]["passage"],
                "question_results": [
                    {
                        "question_id": 1,
                        "is_correct": False,
                        "explanation": {"why_correct": "Reason 1", "grammar_rule": "Rule 1"},
                    },
                    {
                        "question_id": 2,
                        "is_correct": True,
                        "explanation": {"why_correct": "Reason 2", "grammar_rule": "Rule 2"},
                    },
                ],
            }
        ],
    }

    upgrade_to_battle_tested(exam["session_id"], evaluation)
    stats = get_bank_stats()
    assert stats["battle_tested"] == 1
    assert stats["reviewed"] == 0


def test_upgrade_skips_when_explanations_missing(db_path):
    """Contexts stay 'reviewed' if not all questions have explanations."""
    from tools.question_bank import init_db, cache_contexts, upgrade_to_battle_tested, get_bank_stats
    init_db()
    exam = _make_exam(1)
    cache_contexts(exam)

    # Evaluation with one explanation missing (None)
    evaluation = {
        "session_id": exam["session_id"],
        "context_results": [
            {
                "context_id": 1,
                "type": "fill_in_blank",
                "passage": exam["contexts"][0]["passage"],
                "question_results": [
                    {
                        "question_id": 1,
                        "is_correct": True,
                        "explanation": {"why_correct": "R1", "grammar_rule": "G1"},
                    },
                    {
                        "question_id": 2,
                        "is_correct": True,
                        "explanation": None,  # missing
                    },
                ],
            }
        ],
    }

    upgrade_to_battle_tested(exam["session_id"], evaluation)
    stats = get_bank_stats()
    assert stats["reviewed"] == 1
    assert stats["battle_tested"] == 0
