"""Tests for tools/reading_question_bank.py — RC SQLite bank."""
import json
import pytest


@pytest.fixture(autouse=True)
def _isolate_db_and_tracking(monkeypatch, tmp_path):
    """Use a temp DB and tracking file so tests don't touch real data."""
    import tools.reading_question_bank as rqb
    db_path = tmp_path / "reading_question_bank.db"
    monkeypatch.setattr(rqb, "DB_PATH", str(db_path))
    tracking = tmp_path / "system_error_tracking.md"
    monkeypatch.setattr(rqb, "SYSTEM_TRACKING_FILE", str(tracking))


def _q(stem_family="main_idea", correct="A", bolded_term=None, qid=1):
    return {
        "question_id": qid,
        "stem_family": stem_family,
        "question_text": "Quelle est l'idée?",
        "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
        "correct_answer": correct,
        "justification": "Reason.",
        "bolded_term": bolded_term,
    }


def _ctx(context_id=1, passage="Un passage francophone unique.",
         has_signature=False, q=None):
    return {
        "context_id": context_id,
        "passage": passage,
        "has_signature": has_signature,
        "questions": [q or _q(qid=context_id)],
    }


def _exam(contexts):
    return {
        "session_id": "reading_test_session",
        "exam_kind": "reading_comprehension",
        "num_questions": len(contexts),
        "contexts": contexts,
    }


def test_init_db_creates_rc_contexts_table():
    import sqlite3
    from tools.reading_question_bank import init_db, DB_PATH
    init_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='rc_contexts'"
        ).fetchone()
        assert row is not None
        cols = {r[1] for r in conn.execute("PRAGMA table_info(rc_contexts)").fetchall()}
        expected = {
            "context_id", "passage", "has_signature", "question_json",
            "stem_family", "status", "source_session", "created_at",
            "times_served", "passage_hash", "last_incorrect", "user_flags",
        }
        assert expected.issubset(cols)
    finally:
        conn.close()


def test_cache_contexts_inserts_rows():
    import sqlite3
    from tools.reading_question_bank import init_db, cache_contexts, DB_PATH
    init_db()
    cache_contexts(_exam([_ctx(1, "Passage one."), _ctx(2, "Passage two.")]))
    conn = sqlite3.connect(DB_PATH)
    try:
        count = conn.execute("SELECT COUNT(*) FROM rc_contexts").fetchone()[0]
        assert count == 2
    finally:
        conn.close()


def test_cache_contexts_dedup_by_passage_hash():
    import sqlite3
    from tools.reading_question_bank import init_db, cache_contexts, DB_PATH
    init_db()
    cache_contexts(_exam([_ctx(1, "Même passage.")]))
    cache_contexts(_exam([_ctx(1, "Même passage.")]))  # duplicate
    conn = sqlite3.connect(DB_PATH)
    try:
        count = conn.execute("SELECT COUNT(*) FROM rc_contexts").fetchone()[0]
        assert count == 1
    finally:
        conn.close()


def test_cache_contexts_strips_question_id_from_stored_json():
    import sqlite3
    from tools.reading_question_bank import init_db, cache_contexts, DB_PATH
    init_db()
    cache_contexts(_exam([_ctx(1, "Passage.", q=_q(qid=42))]))
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute("SELECT question_json FROM rc_contexts").fetchone()
        stored = json.loads(row[0])
        assert "question_id" not in stored
        assert stored["correct_answer"] == "A"
    finally:
        conn.close()


def test_cache_contexts_writes_stem_family_and_status():
    import sqlite3
    from tools.reading_question_bank import init_db, cache_contexts, DB_PATH
    init_db()
    cache_contexts(_exam([_ctx(1, "P.", q=_q(stem_family="vocabulary", bolded_term="x"))]),
                   status="warned")
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute("SELECT stem_family, status FROM rc_contexts").fetchone()
        assert row[0] == "vocabulary"
        assert row[1] == "warned"
    finally:
        conn.close()


def test_get_bank_stats_empty():
    from tools.reading_question_bank import init_db, get_bank_stats
    init_db()
    stats = get_bank_stats()
    assert stats["total_contexts"] == 0
    assert stats["total_questions"] == 0
    assert stats["reviewed"] == 0
    assert stats["battle_tested"] == 0
    assert stats["warned"] == 0


def test_get_bank_stats_counts_by_status():
    from tools.reading_question_bank import init_db, cache_contexts, get_bank_stats
    init_db()
    cache_contexts(_exam([_ctx(1, "P1")]), status="reviewed")
    cache_contexts(_exam([_ctx(2, "P2")]), status="reviewed")
    cache_contexts(_exam([_ctx(3, "P3")]), status="warned")
    stats = get_bank_stats()
    assert stats["total_contexts"] == 3
    assert stats["total_questions"] == 3  # RC: 1:1 with contexts
    assert stats["reviewed"] == 2
    assert stats["warned"] == 1
    assert stats["battle_tested"] == 0
