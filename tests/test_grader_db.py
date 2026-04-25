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
    old_qb, old_gdb = qb.DB_PATH, gdb.DB_PATH
    qb.DB_PATH = path
    gdb.DB_PATH = path
    yield path
    qb.DB_PATH = old_qb
    gdb.DB_PATH = old_gdb


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


# ── Task 3: get_contexts_for_review ──────────────────────────────────────────

def test_get_contexts_for_review_returns_all(db_path):
    """get_contexts_for_review with no filters returns all contexts."""
    from tools.grader_db import init_reviews_table, get_contexts_for_review

    context_ids = _seed_contexts(db_path, 3)
    init_reviews_table()

    result = get_contexts_for_review({})
    assert result["total"] == 3
    assert len(result["items"]) == 3
    returned_ids = {item["context_id"] for item in result["items"]}
    assert returned_ids == set(context_ids)


def test_get_contexts_for_review_filter_status(db_path):
    """get_contexts_for_review filters by status correctly."""
    from tools.grader_db import init_reviews_table, get_contexts_for_review

    context_ids = _seed_contexts(db_path, 2)
    init_reviews_table()

    # Update one context to 'battle_tested'
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE contexts SET status = 'battle_tested' WHERE context_id = ?",
        (context_ids[0],),
    )
    conn.commit()
    conn.close()

    result = get_contexts_for_review({"status": "reviewed"})
    assert result["total"] == 1
    assert result["items"][0]["context_id"] == context_ids[1]

    result2 = get_contexts_for_review({"status": "battle_tested"})
    assert result2["total"] == 1
    assert result2["items"][0]["context_id"] == context_ids[0]


def test_get_contexts_for_review_filter_flagged(db_path):
    """get_contexts_for_review filters by flagged (user_flags >= 1) correctly."""
    from tools.grader_db import init_reviews_table, get_contexts_for_review

    context_ids = _seed_contexts(db_path, 3)
    init_reviews_table()

    # Flag the first two contexts
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE contexts SET user_flags = 2 WHERE context_id = ?", (context_ids[0],)
    )
    conn.execute(
        "UPDATE contexts SET user_flags = 1 WHERE context_id = ?", (context_ids[1],)
    )
    conn.commit()
    conn.close()

    flagged = get_contexts_for_review({"flagged": "true"})
    assert flagged["total"] == 2

    unflagged = get_contexts_for_review({"flagged": "false"})
    assert unflagged["total"] == 1
    assert unflagged["items"][0]["context_id"] == context_ids[2]


def test_get_contexts_for_review_filter_reviewed(db_path):
    """get_contexts_for_review filters by reviewed (expert_rating IS NOT NULL) correctly."""
    from tools.grader_db import init_reviews_table, get_contexts_for_review, save_review

    context_ids = _seed_contexts(db_path, 3)
    init_reviews_table()

    # Save a review for the first context
    save_review(context_ids[0], "Good", "Looks fine.")

    reviewed = get_contexts_for_review({"reviewed": "true"})
    assert reviewed["total"] == 1
    assert reviewed["items"][0]["context_id"] == context_ids[0]
    assert reviewed["items"][0]["expert_rating"] == "Good"

    unreviewed = get_contexts_for_review({"reviewed": "false"})
    assert unreviewed["total"] == 2
    unreviewed_ids = {item["context_id"] for item in unreviewed["items"]}
    assert context_ids[1] in unreviewed_ids
    assert context_ids[2] in unreviewed_ids


def test_get_contexts_for_review_combined_filters(db_path):
    """get_contexts_for_review applies multiple filters with AND logic."""
    from tools.grader_db import init_reviews_table, get_contexts_for_review, save_review

    context_ids = _seed_contexts(db_path, 4)
    init_reviews_table()

    # context_ids[0]: reviewed=True, flagged=True, status=reviewed
    save_review(context_ids[0], "Good", None)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE contexts SET user_flags = 1 WHERE context_id = ?", (context_ids[0],)
    )
    # context_ids[1]: reviewed=True, flagged=False, status=reviewed
    conn.commit()
    conn.close()
    save_review(context_ids[1], "Bad", "Issues found.")

    # Filter: reviewed=true AND flagged=true
    result = get_contexts_for_review({"reviewed": "true", "flagged": "true"})
    assert result["total"] == 1
    assert result["items"][0]["context_id"] == context_ids[0]

    # Filter: reviewed=false AND status=reviewed
    result2 = get_contexts_for_review({"reviewed": "false", "status": "reviewed"})
    assert result2["total"] == 2
    returned_ids = {item["context_id"] for item in result2["items"]}
    assert context_ids[2] in returned_ids
    assert context_ids[3] in returned_ids


# ── Task 4: get_review and save_review ───────────────────────────────────────

def test_get_review_returns_none_when_missing(db_path):
    """get_review returns None when no review exists for the given context_id."""
    from tools.grader_db import init_reviews_table, get_review

    _seed_contexts(db_path, 1)
    init_reviews_table()

    result = get_review("nonexistent-id")
    assert result is None


def test_get_review_returns_existing_review(db_path):
    """get_review returns the review dict when it exists."""
    from tools.grader_db import init_reviews_table, get_review, save_review

    context_ids = _seed_contexts(db_path, 1)
    init_reviews_table()

    save_review(context_ids[0], "Good", "Very clear questions.")

    review = get_review(context_ids[0])
    assert review is not None
    assert review["context_id"] == context_ids[0]
    assert review["expert_rating"] == "Good"
    assert review["expert_critique"] == "Very clear questions."
    assert review["model_output"] is not None  # snapshot was stored
    assert review["created_at"] is not None
    assert review["updated_at"] is not None


def test_save_review_creates_snapshot_on_first_save(db_path):
    """save_review stores a context snapshot in model_output on first insert."""
    from tools.grader_db import init_reviews_table, save_review, get_review

    context_ids = _seed_contexts(db_path, 1)
    init_reviews_table()

    result = save_review(context_ids[0], "Good", "OK")
    assert result is not None
    assert "updated_at" in result

    review = get_review(context_ids[0])
    assert review is not None

    snapshot = json.loads(review["model_output"])
    assert snapshot["context_id"] == context_ids[0]
    assert "passage" in snapshot
    assert "questions" in snapshot
    assert "grammar_topics" in snapshot
    assert "type" in snapshot
    assert "status" in snapshot


def test_save_review_updates_existing_review(db_path):
    """save_review updates rating, critique, and updated_at on subsequent calls."""
    from tools.grader_db import init_reviews_table, save_review, get_review

    context_ids = _seed_contexts(db_path, 1)
    init_reviews_table()

    first_result = save_review(context_ids[0], "Good", "Initial critique.")
    assert first_result is not None

    second_result = save_review(context_ids[0], "Bad", "Updated critique.")
    assert second_result is not None

    review = get_review(context_ids[0])
    assert review["expert_rating"] == "Bad"
    assert review["expert_critique"] == "Updated critique."
    assert review["updated_at"] is not None

    # Verify only one row exists
    conn = sqlite3.connect(db_path)
    count = conn.execute(
        "SELECT COUNT(*) FROM reviews WHERE context_id = ?", (context_ids[0],)
    ).fetchone()[0]
    conn.close()
    assert count == 1


def test_save_review_without_critique(db_path):
    """save_review accepts None for expert_critique."""
    from tools.grader_db import init_reviews_table, save_review, get_review

    context_ids = _seed_contexts(db_path, 1)
    init_reviews_table()

    result = save_review(context_ids[0], "Good", None)
    assert result is not None

    review = get_review(context_ids[0])
    assert review["expert_rating"] == "Good"
    assert review["expert_critique"] is None


def test_save_review_returns_none_for_missing_context(db_path):
    """save_review returns None when context_id does not exist in contexts table."""
    from tools.grader_db import init_reviews_table, save_review

    _seed_contexts(db_path, 0)
    init_reviews_table()

    result = save_review("does-not-exist", "Good", "critique")
    assert result is None


# ── Task 5: snapshot staleness detection ─────────────────────────────────────

def test_is_snapshot_outdated_returns_false_when_unchanged(db_path):
    """is_snapshot_outdated returns False when context data matches the snapshot."""
    from tools.grader_db import init_reviews_table, save_review, is_snapshot_outdated

    context_ids = _seed_contexts(db_path, 1)
    init_reviews_table()

    save_review(context_ids[0], "Good", None)

    result = is_snapshot_outdated(context_ids[0])
    assert result is False


def test_is_snapshot_outdated_returns_true_when_passage_changed(db_path):
    """is_snapshot_outdated returns True when the context passage has changed."""
    from tools.grader_db import init_reviews_table, save_review, is_snapshot_outdated

    context_ids = _seed_contexts(db_path, 1)
    init_reviews_table()

    # Save review (snapshot taken now)
    save_review(context_ids[0], "Good", None)

    # Mutate the passage in contexts table
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE contexts SET passage = 'Completely different passage text.' WHERE context_id = ?",
        (context_ids[0],),
    )
    conn.commit()
    conn.close()

    result = is_snapshot_outdated(context_ids[0])
    assert result is True


def test_is_snapshot_outdated_returns_none_when_no_review(db_path):
    """is_snapshot_outdated returns None when no review exists for context_id."""
    from tools.grader_db import init_reviews_table, is_snapshot_outdated

    context_ids = _seed_contexts(db_path, 1)
    init_reviews_table()

    result = is_snapshot_outdated(context_ids[0])
    assert result is None


def test_get_contexts_for_review_includes_type(db_path):
    """get_contexts_for_review items include context type."""
    from tools.grader_db import init_reviews_table, get_contexts_for_review
    _seed_contexts(db_path, 3)
    init_reviews_table()
    result = get_contexts_for_review({})
    for item in result["items"]:
        assert "type" in item
        assert item["type"] in ("fill_in_blank", "error_identification")


def test_is_snapshot_outdated_returns_none_when_context_deleted(db_path):
    """is_snapshot_outdated returns None when context has been deleted from contexts table."""
    from tools.grader_db import init_reviews_table, save_review, is_snapshot_outdated

    context_ids = _seed_contexts(db_path, 1)
    init_reviews_table()

    save_review(context_ids[0], "Good", None)

    # Delete the context from contexts table
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM contexts WHERE context_id = ?", (context_ids[0],))
    conn.commit()
    conn.close()

    result = is_snapshot_outdated(context_ids[0])
    assert result is None


# ── Task LLM Evaluator: save_llm_review and cleanup fix ──────────────────────

def test_save_llm_review_insert(db_path):
    """save_llm_review inserts a new row when no review exists."""
    from tools.grader_db import init_reviews_table, save_llm_review, get_review

    context_ids = _seed_contexts(db_path, 1)
    init_reviews_table()

    result = save_llm_review(context_ids[0], "Good", "Well-formed question.")

    assert result is not None
    assert "updated_at" in result

    row = get_review(context_ids[0])
    assert row is not None
    assert row["llm_evaluator_rating"] == "Good"
    assert row["llm_evaluator_critique"] == "Well-formed question."
    assert row["expert_rating"] is None


def test_save_llm_review_update_existing_row(db_path):
    """save_llm_review updates only llm fields when an expert review row already exists."""
    from tools.grader_db import init_reviews_table, save_llm_review, save_review, get_review

    context_ids = _seed_contexts(db_path, 1)
    init_reviews_table()

    save_review(context_ids[0], "Good", "Expert says good.")
    result = save_llm_review(context_ids[0], "Bad", "LLM says bad.")

    assert result is not None
    row = get_review(context_ids[0])
    assert row["llm_evaluator_rating"] == "Bad"
    assert row["llm_evaluator_critique"] == "LLM says bad."
    assert row["expert_rating"] == "Good"
    assert row["expert_critique"] == "Expert says good."


def test_save_llm_review_returns_none_for_missing_context(db_path):
    """save_llm_review returns None when context_id is not in the contexts table."""
    from tools.grader_db import init_reviews_table, save_llm_review
    from tools.question_bank import init_db

    init_db()
    init_reviews_table()

    result = save_llm_review("nonexistent-id", "Good", "Some critique")
    assert result is None


def test_cleanup_empty_reviews_preserves_llm_only_rows(db_path):
    """cleanup_empty_reviews must NOT delete rows that have llm_evaluator_rating set."""
    from tools.grader_db import init_reviews_table, save_llm_review, cleanup_empty_reviews, get_review

    context_ids = _seed_contexts(db_path, 1)
    init_reviews_table()

    save_llm_review(context_ids[0], "Good", "LLM critique.")

    deleted = cleanup_empty_reviews()
    assert deleted == 0

    row = get_review(context_ids[0])
    assert row is not None


def test_save_llm_review_rejects_invalid_rating(db_path):
    """save_llm_review raises ValueError for an invalid llm_rating value."""
    from tools.grader_db import init_reviews_table, save_llm_review
    from tools.question_bank import init_db

    init_db()
    init_reviews_table()

    with pytest.raises(ValueError, match="llm_rating must be"):
        save_llm_review("any-id", "invalid", "some critique")
