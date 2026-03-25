# tests/test_question_bank.py
"""Tests for tools/question_bank.py"""
import json
import os
import sqlite3
import tempfile
from unittest.mock import patch, MagicMock
import pytest


@pytest.fixture
def db_path(tmp_path):
    """Provide a temporary database path and patch DB_PATH."""
    path = str(tmp_path / "test_question_bank.db")
    import tools.question_bank as qb
    qb.DB_PATH = path
    yield path


def test_init_db_creates_table(db_path):
    """init_db creates the contexts table with expected columns including user_flags."""
    from tools.question_bank import init_db
    init_db()
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("PRAGMA table_info(contexts)")
    columns = {row[1] for row in cursor.fetchall()}
    conn.close()
    expected = {"context_id", "type", "passage", "questions_json", "num_questions",
                "grammar_topics", "status", "source_session", "created_at",
                "times_served", "passage_hash", "last_incorrect", "user_flags"}
    assert expected == columns


def test_init_db_migrates_old_schema(db_path):
    """init_db drops and recreates DB when user_flags column is missing."""
    import sqlite3
    from tools.question_bank import init_db
    # Create old-schema table (no user_flags)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE contexts (
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
    conn.execute("INSERT INTO contexts VALUES ('old', 'fill_in_blank', 'p', '[]', 0, '', 'reviewed', 's', '2026-01-01', 0, 'h', 0)")
    conn.commit()
    conn.close()

    # init_db should detect missing column and recreate
    init_db()

    conn = sqlite3.connect(db_path)
    cursor = conn.execute("PRAGMA table_info(contexts)")
    columns = {row[1] for row in cursor.fetchall()}
    conn.close()
    assert "user_flags" in columns
    # Old data should be gone (DB was recreated)
    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM contexts").fetchone()[0]
    conn.close()
    assert count == 0


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


def test_cache_contexts_preserves_explanations(db_path):
    """cache_contexts preserves AI-generated explanations in questions_json."""
    from tools.question_bank import init_db, cache_contexts
    init_db()
    exam = _make_exam(1)
    # Add explanations to questions (as generate_exam will now produce)
    for ctx in exam["contexts"]:
        for q in ctx["questions"]:
            q["explanation"] = {"why_correct": "Reason", "grammar_rule": "Rule"}
    cache_contexts(exam)

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT questions_json FROM contexts").fetchone()
    conn.close()
    questions = json.loads(row[0])
    assert questions[0]["explanation"] == {"why_correct": "Reason", "grammar_rule": "Rule"}


def test_cache_contexts_warned_status(db_path):
    """cache_contexts stores warned status correctly."""
    from tools.question_bank import init_db, cache_contexts, get_bank_stats
    init_db()
    exam = _make_exam(1)
    cache_contexts(exam, status="warned")
    stats = get_bank_stats()
    assert stats["warned"] == 1
    assert stats["reviewed"] == 0


def test_get_bank_stats_includes_warned(db_path):
    """get_bank_stats returns warned count alongside reviewed and battle_tested."""
    from tools.question_bank import init_db, cache_contexts, get_bank_stats
    init_db()
    exam1 = _make_exam(1)
    cache_contexts(exam1, status="reviewed")
    exam2 = {
        "session_id": "s2", "timestamp": "t", "num_questions": 1,
        "contexts": [{
            "context_id": 1, "type": "fill_in_blank",
            "passage": "Different passage for warned context.",
            "questions": [{"question_id": 1, "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
                          "correct_answer": "A", "grammar_topic": "tense"}],
        }],
    }
    cache_contexts(exam2, status="warned")
    stats = get_bank_stats()
    assert stats["reviewed"] == 1
    assert stats["warned"] == 1


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


# ── Task 4: assemble_exam_from_cache ────────────────────────────────────────

def _make_large_exam():
    """Helper: build an exam with 10 questions across diverse topics and types."""
    topics = ["agreement", "conjugation", "preposition", "vocabulary", "tense",
              "pronoun", "conjunction", "spelling", "syntax", "adverb"]
    contexts = []
    qid = 1
    for i in range(1, 9):  # 8 contexts
        ctx_type = "fill_in_blank" if i <= 5 else "error_identification"
        num_q = 2 if (ctx_type == "fill_in_blank" and i <= 2) else 1
        questions = []
        for _ in range(num_q):
            questions.append({
                "question_id": qid,
                "options": {"A": f"a{qid}", "B": f"b{qid}", "C": f"c{qid}", "D": f"d{qid}"},
                "correct_answer": "A",
                "grammar_topic": topics[(qid - 1) % len(topics)],
            })
            qid += 1
        passage = f"Unique passage {i} with ({questions[0]['question_id']}) _______________ blank."
        contexts.append({
            "context_id": i,
            "type": ctx_type,
            "passage": passage,
            "questions": questions,
        })
    return {
        "session_id": "exam_20260318_130000",
        "timestamp": "2026-03-18T13:00:00",
        "num_questions": qid - 1,
        "contexts": contexts,
    }


def test_assemble_exam_returns_none_when_empty(db_path):
    """assemble_exam_from_cache returns None exam when bank is empty."""
    from tools.question_bank import init_db, assemble_exam_from_cache
    init_db()
    result = assemble_exam_from_cache(10)
    assert result["exam"] is None
    assert result["available_questions"] == 0


def test_assemble_exam_returns_valid_exam(db_path):
    """assemble_exam_from_cache returns a properly structured exam dict."""
    from tools.question_bank import init_db, cache_contexts, assemble_exam_from_cache
    init_db()
    cache_contexts(_make_large_exam())
    result = assemble_exam_from_cache(5)
    exam = result["exam"]
    assert exam is not None
    assert exam["source"] == "cache"
    assert "session_id" in exam
    assert "contexts" in exam
    # Question IDs must be continuous starting from 1
    qids = [q["question_id"] for ctx in exam["contexts"] for q in ctx["questions"]]
    assert qids == list(range(1, len(qids) + 1))
    # Context IDs must be sequential starting from 1
    cids = [ctx["context_id"] for ctx in exam["contexts"]]
    assert cids == list(range(1, len(cids) + 1))
    # Total questions should not exceed target by more than 1 (best-fit strategy)
    assert len(qids) <= 6  # target 5 + 1 max overshoot


def test_assemble_exam_best_fit_strategy(db_path):
    """Assembled exam uses best-fit: exact, then target-1, then target+1 (never exceed by more than 1)."""
    from tools.question_bank import init_db, cache_contexts, assemble_exam_from_cache
    init_db()
    cache_contexts(_make_large_exam())
    for target in [5, 7, 10]:
        result = assemble_exam_from_cache(target)
        if result["exam"]:
            total_q = sum(len(ctx["questions"]) for ctx in result["exam"]["contexts"])
            assert total_q <= target + 1  # best-fit allows at most +1


def test_assemble_exam_enforces_type_mix(db_path):
    """Assembled exam has both fill-in-blank and error identification contexts."""
    from tools.question_bank import init_db, cache_contexts, assemble_exam_from_cache
    init_db()
    cache_contexts(_make_large_exam())  # has both types
    result = assemble_exam_from_cache(6)
    exam = result["exam"]
    assert exam is not None
    types = [ctx["type"] for ctx in exam["contexts"]]
    assert "fill_in_blank" in types
    assert "error_identification" in types


def test_assemble_exam_battle_tested_carries_explanations(db_path):
    """Assembled exam from battle_tested contexts includes pre-baked explanations."""
    from tools.question_bank import init_db, cache_contexts, upgrade_to_battle_tested, assemble_exam_from_cache
    init_db()
    exam = _make_large_exam()
    cache_contexts(exam)

    # Upgrade all contexts with explanations
    evaluation = {"session_id": exam["session_id"], "context_results": []}
    for ctx in exam["contexts"]:
        ctx_r = {"context_id": ctx["context_id"], "type": ctx["type"], "passage": ctx["passage"], "question_results": []}
        for q in ctx["questions"]:
            ctx_r["question_results"].append({
                "question_id": q["question_id"],
                "is_correct": False,
                "explanation": {"why_correct": "Reason", "grammar_rule": "Rule"},
            })
        evaluation["context_results"].append(ctx_r)
    upgrade_to_battle_tested(exam["session_id"], evaluation)

    result = assemble_exam_from_cache(5)
    assert result["exam"] is not None
    for ctx in result["exam"]["contexts"]:
        for q in ctx["questions"]:
            assert q["explanation"] is not None
            assert q["explanation"]["why_correct"] == "Reason"


def test_assemble_exam_renumbers_passage_blanks(db_path):
    """Fill-in-blank passage blank markers are renumbered to match new question_ids."""
    from tools.question_bank import init_db, cache_contexts, assemble_exam_from_cache
    init_db()
    # Create exam where context has question_id=5
    exam = {
        "session_id": "exam_renum_test",
        "timestamp": "2026-03-18T14:00:00",
        "num_questions": 1,
        "contexts": [{
            "context_id": 1,
            "type": "fill_in_blank",
            "passage": "Please fill (5) _______________ here.",
            "questions": [{
                "question_id": 5,
                "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
                "correct_answer": "A",
                "grammar_topic": "preposition",
            }],
        }],
    }
    cache_contexts(exam)
    result = assemble_exam_from_cache(1)
    assert result["exam"] is not None
    # After assembly, question_id should be 1, and passage should say (1)
    ctx = result["exam"]["contexts"][0]
    assert "(1)" in ctx["passage"]
    assert "(5)" not in ctx["passage"]
    # bank_context_id (UUID) must be preserved for post-exam updates
    assert ctx["bank_context_id"] is not None
    # original_passage_hash must be stored as fallback for post-exam matching
    assert ctx["original_passage_hash"] is not None


# ── Task 5: prefill_bank ────────────────────────────────────────────────────

def test_prefill_bank_generates_and_caches(db_path):
    """prefill_bank calls generate_exam, review_exam_quality, and cache_contexts."""
    from tools.question_bank import init_db, prefill_bank, get_bank_stats
    from tools.model_config import ModelConfig
    init_db()

    exam = _make_exam(2)
    review_result = {"passed": True, "flagged_questions": [], "summary": "OK"}
    configs = {
        "generate": ModelConfig(api_key="k", base_url="u", model="m"),
        "review": ModelConfig(api_key="k", base_url="u", model="m"),
    }

    with patch("tools.generate_exam.generate_exam", return_value=exam) as mock_gen, \
         patch("tools.review_exam.review_exam_quality", return_value=review_result) as mock_rev:
        prefill_bank(10, configs)

    mock_gen.assert_called_once_with(10, model_config=configs["generate"])
    mock_rev.assert_called_once_with(exam, model_config=configs["review"])
    stats = get_bank_stats()
    assert stats["total_contexts"] == 2


# ── Task 9: update_last_incorrect ───────────────────────────────────────────

def test_update_last_incorrect_by_bank_context_id(db_path):
    """update_last_incorrect sets flag using bank_context_id for cached exams."""
    from tools.question_bank import init_db, cache_contexts, update_last_incorrect
    init_db()
    exam = _make_exam(1)
    cache_contexts(exam)

    # Get the bank UUID assigned during caching
    import sqlite3
    conn = sqlite3.connect(db_path)
    bank_id = conn.execute("SELECT context_id FROM contexts").fetchone()[0]
    conn.close()

    evaluation = {
        "session_id": exam["session_id"],
        "context_results": [
            {
                "context_id": 1,
                "type": "fill_in_blank",
                "passage": "renumbered passage that won't hash-match",
                "bank_context_id": bank_id,
                "question_results": [
                    {"question_id": 1, "is_correct": False, "explanation": None},
                    {"question_id": 2, "is_correct": True, "explanation": None},
                ],
            }
        ],
    }

    update_last_incorrect(evaluation)

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT last_incorrect FROM contexts").fetchone()
    conn.close()
    assert row[0] == 1


def test_update_last_incorrect_falls_back_to_hash(db_path):
    """update_last_incorrect falls back to passage hash for fresh exams."""
    from tools.question_bank import init_db, cache_contexts, update_last_incorrect
    init_db()
    exam = _make_exam(1)
    cache_contexts(exam)

    evaluation = {
        "session_id": exam["session_id"],
        "context_results": [
            {
                "context_id": 1,
                "type": "fill_in_blank",
                "passage": exam["contexts"][0]["passage"],
                "question_results": [
                    {"question_id": 1, "is_correct": False, "explanation": None},
                    {"question_id": 2, "is_correct": True, "explanation": None},
                ],
            }
        ],
    }

    update_last_incorrect(evaluation)

    import sqlite3
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT last_incorrect FROM contexts").fetchone()
    conn.close()
    assert row[0] == 1


def test_update_last_incorrect_resets_from_one_to_zero(db_path):
    """update_last_incorrect resets flag from 1 to 0 on a subsequent all-correct attempt."""
    from tools.question_bank import init_db, cache_contexts, update_last_incorrect
    init_db()
    exam = _make_exam(1)
    cache_contexts(exam)

    import sqlite3

    # First attempt: incorrect
    evaluation_wrong = {
        "session_id": exam["session_id"],
        "context_results": [
            {
                "context_id": 1,
                "type": "fill_in_blank",
                "passage": exam["contexts"][0]["passage"],
                "question_results": [
                    {"question_id": 1, "is_correct": False, "explanation": None},
                    {"question_id": 2, "is_correct": True, "explanation": None},
                ],
            }
        ],
    }
    update_last_incorrect(evaluation_wrong)
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT last_incorrect FROM contexts").fetchone()[0] == 1
    conn.close()

    # Second attempt: all correct
    evaluation_right = {
        "session_id": exam["session_id"],
        "context_results": [
            {
                "context_id": 1,
                "type": "fill_in_blank",
                "passage": exam["contexts"][0]["passage"],
                "question_results": [
                    {"question_id": 1, "is_correct": True, "explanation": None},
                    {"question_id": 2, "is_correct": True, "explanation": None},
                ],
            }
        ],
    }
    update_last_incorrect(evaluation_right)
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT last_incorrect FROM contexts").fetchone()[0] == 0
    conn.close()
