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
         has_signature=False, q=None, topic=""):
    return {
        "context_id": context_id,
        "passage": passage,
        "topic": topic,
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
            "topic",
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


def test_assemble_empty_bank_returns_none_exam():
    from tools.reading_question_bank import init_db, assemble_exam_from_cache
    init_db()
    result = assemble_exam_from_cache(3)
    assert result["exam"] is None
    assert result["available_questions"] == 0


def test_assemble_returns_exam_dict_with_renumbered_ids():
    from tools.reading_question_bank import init_db, cache_contexts, assemble_exam_from_cache
    init_db()
    cache_contexts(_exam([_ctx(1, "P1"), _ctx(2, "P2")]))
    result = assemble_exam_from_cache(2)
    exam = result["exam"]
    assert exam is not None
    assert exam["source"] == "cache"
    assert exam["exam_kind"] == "reading_comprehension"
    assert [c["context_id"] for c in exam["contexts"]] == [1, 2]
    qids = [c["questions"][0]["question_id"] for c in exam["contexts"]]
    assert qids == [1, 2]


def test_assemble_propagates_topic():
    """Cached exams carry the same topic field fresh exams are required to have."""
    from tools.reading_question_bank import init_db, cache_contexts, assemble_exam_from_cache
    init_db()
    cache_contexts(_exam([_ctx(1, "P sujet.", topic="Le recyclage municipal")]))
    result = assemble_exam_from_cache(1)
    assert result["exam"]["contexts"][0]["topic"] == "Le recyclage municipal"


def test_assemble_propagates_bank_context_id_and_passage_hash():
    from tools.reading_question_bank import init_db, cache_contexts, assemble_exam_from_cache
    init_db()
    cache_contexts(_exam([_ctx(1, "Unique passage X.")]))
    result = assemble_exam_from_cache(1)
    ctx = result["exam"]["contexts"][0]
    assert ctx["bank_context_id"]
    assert ctx["original_passage_hash"]
    assert ctx["bank_status"] == "reviewed"


def test_assemble_increments_times_served():
    import sqlite3
    from tools.reading_question_bank import init_db, cache_contexts, assemble_exam_from_cache, DB_PATH
    init_db()
    cache_contexts(_exam([_ctx(1, "P1")]))
    assemble_exam_from_cache(1)
    conn = sqlite3.connect(DB_PATH)
    try:
        served = conn.execute("SELECT times_served FROM rc_contexts").fetchone()[0]
        assert served == 1
    finally:
        conn.close()


def test_assemble_prefers_reviewed_over_battle_tested_over_warned():
    from tools.reading_question_bank import init_db, cache_contexts, assemble_exam_from_cache
    init_db()
    cache_contexts(_exam([_ctx(1, "reviewed_p")]), status="reviewed")
    cache_contexts(_exam([_ctx(2, "battle_p")]), status="battle_tested")
    cache_contexts(_exam([_ctx(3, "warned_p")]), status="warned")
    result = assemble_exam_from_cache(1)
    assert result["exam"]["contexts"][0]["passage"] == "reviewed_p"


def test_assemble_deprioritizes_user_flagged():
    from tools.reading_question_bank import (
        init_db, cache_contexts, assemble_exam_from_cache, flag_context, _passage_hash
    )
    init_db()
    cache_contexts(_exam([_ctx(1, "flagged_p")]))
    cache_contexts(_exam([_ctx(2, "clean_p")]))
    flag_context(passage_hash=_passage_hash("flagged_p"), category="test")
    result = assemble_exam_from_cache(1)
    assert result["exam"]["contexts"][0]["passage"] == "clean_p"


def test_assemble_times_served_beats_status():
    import sqlite3
    from tools.reading_question_bank import init_db, cache_contexts, assemble_exam_from_cache, DB_PATH
    init_db()
    cache_contexts(_exam([_ctx(1, "served_reviewed_p")]), status="reviewed")
    cache_contexts(_exam([_ctx(2, "fresh_warned_p")]), status="warned")
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("UPDATE rc_contexts SET times_served = 1 WHERE passage = 'served_reviewed_p'")
        conn.commit()
    finally:
        conn.close()
    result = assemble_exam_from_cache(1)
    assert result["exam"]["contexts"][0]["passage"] == "fresh_warned_p"


def test_assemble_rotates_through_bank_before_repeating():
    from tools.reading_question_bank import init_db, cache_contexts, assemble_exam_from_cache
    init_db()
    for i in range(4):
        cache_contexts(_exam([_ctx(i + 1, f"P{i + 1}")]))
    first = {c["passage"] for c in assemble_exam_from_cache(2)["exam"]["contexts"]}
    second = {c["passage"] for c in assemble_exam_from_cache(2)["exam"]["contexts"]}
    assert first.isdisjoint(second)
    assert first | second == {"P1", "P2", "P3", "P4"}


def test_assemble_shuffles_final_exam_order(monkeypatch):
    import sqlite3
    import tools.reading_question_bank as rqb
    from tools.reading_question_bank import init_db, cache_contexts, assemble_exam_from_cache, DB_PATH
    init_db()
    for i in range(3):
        cache_contexts(_exam([_ctx(i + 1, f"P{i + 1}")]))
    conn = sqlite3.connect(DB_PATH)
    try:
        # Distinct times_served pins selection order to P1, P2, P3.
        for i in range(3):
            conn.execute("UPDATE rc_contexts SET times_served = ? WHERE passage = ?",
                         (i, f"P{i + 1}"))
        conn.commit()
    finally:
        conn.close()
    monkeypatch.setattr(rqb.random, "shuffle", lambda seq: seq.reverse())
    ordered = [c["passage"] for c in assemble_exam_from_cache(3)["exam"]["contexts"]]
    assert ordered == ["P3", "P2", "P1"]


def _eval_ctx(context_id, bank_context_id=None, original_passage_hash=None,
              passage="P", is_correct=True):
    return {
        "context_id": context_id,
        "passage": passage,
        "bank_context_id": bank_context_id,
        "original_passage_hash": original_passage_hash,
        "question_results": [
            {"question_id": context_id, "is_correct": is_correct,
             "user_answer": "A", "correct_answer": "A" if is_correct else "B"}
        ],
    }


def test_upgrade_promotes_reviewed_to_battle_tested():
    import sqlite3
    from tools.reading_question_bank import (
        init_db, cache_contexts, assemble_exam_from_cache,
        upgrade_to_battle_tested, DB_PATH,
    )
    init_db()
    cache_contexts(_exam([_ctx(1, "P1")]))
    assembled = assemble_exam_from_cache(1)["exam"]
    bank_id = assembled["contexts"][0]["bank_context_id"]

    evaluation = {"context_results": [_eval_ctx(1, bank_context_id=bank_id, passage="P1")]}
    upgrade_to_battle_tested(assembled["session_id"], evaluation)

    conn = sqlite3.connect(DB_PATH)
    try:
        status = conn.execute("SELECT status FROM rc_contexts WHERE context_id = ?",
                              (bank_id,)).fetchone()[0]
        assert status == "battle_tested"
    finally:
        conn.close()


def test_upgrade_does_not_promote_warned():
    import sqlite3
    from tools.reading_question_bank import (
        init_db, cache_contexts, assemble_exam_from_cache,
        upgrade_to_battle_tested, DB_PATH,
    )
    init_db()
    cache_contexts(_exam([_ctx(1, "P1")]), status="warned")
    assembled = assemble_exam_from_cache(1)["exam"]
    bank_id = assembled["contexts"][0]["bank_context_id"]

    evaluation = {"context_results": [_eval_ctx(1, bank_context_id=bank_id, passage="P1")]}
    upgrade_to_battle_tested(assembled["session_id"], evaluation)

    conn = sqlite3.connect(DB_PATH)
    try:
        status = conn.execute("SELECT status FROM rc_contexts WHERE context_id = ?",
                              (bank_id,)).fetchone()[0]
        assert status == "warned"
    finally:
        conn.close()


def test_update_last_incorrect_sets_flag_by_bank_id():
    import sqlite3
    from tools.reading_question_bank import (
        init_db, cache_contexts, assemble_exam_from_cache,
        update_last_incorrect, DB_PATH,
    )
    init_db()
    cache_contexts(_exam([_ctx(1, "P1")]))
    assembled = assemble_exam_from_cache(1)["exam"]
    bank_id = assembled["contexts"][0]["bank_context_id"]

    evaluation = {"context_results": [_eval_ctx(1, bank_context_id=bank_id,
                                                 passage="P1", is_correct=False)]}
    update_last_incorrect(evaluation)

    conn = sqlite3.connect(DB_PATH)
    try:
        flag = conn.execute("SELECT last_incorrect FROM rc_contexts WHERE context_id = ?",
                            (bank_id,)).fetchone()[0]
        assert flag == 1
    finally:
        conn.close()


def test_update_last_incorrect_clears_when_all_correct():
    import sqlite3
    from tools.reading_question_bank import (
        init_db, cache_contexts, assemble_exam_from_cache,
        update_last_incorrect, DB_PATH,
    )
    init_db()
    cache_contexts(_exam([_ctx(1, "P1")]))
    assembled = assemble_exam_from_cache(1)["exam"]
    bank_id = assembled["contexts"][0]["bank_context_id"]
    update_last_incorrect({"context_results": [_eval_ctx(1, bank_context_id=bank_id,
                                                          is_correct=False)]})
    update_last_incorrect({"context_results": [_eval_ctx(1, bank_context_id=bank_id,
                                                          is_correct=True)]})
    conn = sqlite3.connect(DB_PATH)
    try:
        flag = conn.execute("SELECT last_incorrect FROM rc_contexts WHERE context_id = ?",
                            (bank_id,)).fetchone()[0]
        assert flag == 0
    finally:
        conn.close()


def test_flag_context_writes_tracking_file():
    import os
    from tools.reading_question_bank import (
        init_db, cache_contexts, flag_context, SYSTEM_TRACKING_FILE, _passage_hash
    )
    init_db()
    cache_contexts(_exam([_ctx(1, "FlagMe")]))
    flag_context(passage_hash=_passage_hash("FlagMe"), category="Wrong answer key")
    assert os.path.exists(SYSTEM_TRACKING_FILE)
    with open(SYSTEM_TRACKING_FILE, encoding="utf-8") as f:
        content = f.read()
    assert "Wrong answer key" in content


def test_init_db_migrates_old_schema_adding_topic_preserving_rows():
    """An existing DB without the topic column gains it without losing rows."""
    import sqlite3
    from tools.reading_question_bank import init_db, DB_PATH
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            CREATE TABLE rc_contexts (
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
        conn.execute(
            "INSERT INTO rc_contexts (context_id, passage, question_json, stem_family, "
            "source_session, created_at, passage_hash) VALUES ('id1', 'P', '{}', "
            "'main_idea', 's', '2026-01-01', 'h1')"
        )
        conn.commit()
    finally:
        conn.close()

    init_db()

    conn = sqlite3.connect(DB_PATH)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(rc_contexts)").fetchall()}
        assert "topic" in cols
        count = conn.execute("SELECT COUNT(*) FROM rc_contexts").fetchone()[0]
        assert count == 1
    finally:
        conn.close()


def test_cache_contexts_stores_topic():
    import sqlite3
    from tools.reading_question_bank import init_db, cache_contexts, DB_PATH
    init_db()
    cache_contexts(_exam([_ctx(1, "P topique.", topic="Le recyclage municipal")]))
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute("SELECT topic FROM rc_contexts").fetchone()
        assert row[0] == "Le recyclage municipal"
    finally:
        conn.close()


def test_get_recent_topics_returns_distinct_recent():
    from tools.reading_question_bank import init_db, cache_contexts, get_recent_topics
    init_db()
    cache_contexts(_exam([
        _ctx(1, "P1", topic="Recyclage"),
        _ctx(2, "P2", topic="Télétravail"),
        _ctx(3, "P3", topic="Recyclage"),  # duplicate topic, distinct passage
    ]))
    topics = get_recent_topics()
    assert topics.count("Recyclage") == 1
    assert set(topics) == {"Recyclage", "Télétravail"}


def test_get_recent_topics_skips_empty_and_respects_limit():
    from tools.reading_question_bank import init_db, cache_contexts, get_recent_topics
    init_db()
    cache_contexts(_exam([_ctx(1, "Sans sujet")]))  # topic defaults to ""
    for i in range(5):
        cache_contexts(_exam([_ctx(i + 2, f"P{i + 2}", topic=f"Sujet {i + 2}")]))
    topics = get_recent_topics(limit=3)
    assert len(topics) == 3
    assert "" not in topics
    # most recently cached topics come first
    assert topics[0] == "Sujet 6"


def test_prefill_passes_recent_topics_to_generator(monkeypatch):
    import tools.reading_question_bank as rqb
    from tools.reading_question_bank import init_db, cache_contexts, prefill_bank
    init_db()
    cache_contexts(_exam([_ctx(1, "Déjà en banque", topic="Recyclage")]))

    captured = {}

    def fake_gen(n, model_config, avoid_topics=None):
        captured["avoid_topics"] = avoid_topics
        return _exam([_ctx(2, " ".join(["mot"] * 100), topic="Télétravail")])

    monkeypatch.setattr(rqb, "_generate_reading_exam", fake_gen)
    monkeypatch.setattr(rqb, "_review_reading_exam",
                        lambda e: {"flagged_questions": []})
    prefill_bank(1, model_config=None)
    assert "Recyclage" in captured["avoid_topics"]


def test_prefill_caches_clean_contexts_as_reviewed(monkeypatch):
    """Stub generate+review so no API call happens."""
    import tools.reading_question_bank as rqb
    from tools.reading_question_bank import init_db, prefill_bank, get_bank_stats

    init_db()
    clean_exam = _exam([
        _ctx(i + 1, " ".join(["mot"] * 100) + f" extra {i}")
        for i in range(3)
    ])
    monkeypatch.setattr(rqb, "_generate_reading_exam",
                        lambda n, model_config, avoid_topics=None: clean_exam)
    monkeypatch.setattr(rqb, "_review_reading_exam",
                        lambda exam: {"flagged_questions": []})

    result = prefill_bank(3, model_config=None)
    assert result["success"] is True
    stats = get_bank_stats()
    assert stats["reviewed"] == 3
    assert stats["warned"] == 0


def test_prefill_caches_warned_when_warning_flagged(monkeypatch):
    import tools.reading_question_bank as rqb
    from tools.reading_question_bank import init_db, prefill_bank, get_bank_stats

    init_db()
    exam = _exam([_ctx(i + 1, " ".join(["mot"] * 100) + f" v{i}") for i in range(2)])
    monkeypatch.setattr(rqb, "_generate_reading_exam",
                        lambda n, model_config, avoid_topics=None: exam)
    monkeypatch.setattr(rqb, "_review_reading_exam",
                        lambda e: {"flagged_questions": [
                            {"context_id": 1, "severity": "warning", "category": "x", "issue": ""},
                        ]})
    prefill_bank(2, model_config=None)
    stats = get_bank_stats()
    assert stats["warned"] == 1
    assert stats["reviewed"] == 1


def test_prefill_excludes_critical_contexts(monkeypatch):
    import tools.reading_question_bank as rqb
    from tools.reading_question_bank import init_db, prefill_bank, get_bank_stats

    init_db()
    exam = _exam([_ctx(i + 1, " ".join(["mot"] * 100) + f" w{i}") for i in range(3)])
    monkeypatch.setattr(rqb, "_generate_reading_exam",
                        lambda n, model_config, avoid_topics=None: exam)
    monkeypatch.setattr(rqb, "_review_reading_exam",
                        lambda e: {"flagged_questions": [
                            {"context_id": 2, "severity": "critical", "category": "x", "issue": ""},
                        ]})
    result = prefill_bank(3, model_config=None)
    assert result["success"] is True
    stats = get_bank_stats()
    assert stats["total_contexts"] == 2  # context_id=2 excluded


def test_prefill_returns_failure_when_all_critical(monkeypatch):
    import tools.reading_question_bank as rqb
    from tools.reading_question_bank import init_db, prefill_bank, get_bank_stats

    init_db()
    exam = _exam([_ctx(i + 1, f"P {i}") for i in range(2)])
    monkeypatch.setattr(rqb, "_generate_reading_exam",
                        lambda n, model_config, avoid_topics=None: exam)
    monkeypatch.setattr(rqb, "_review_reading_exam",
                        lambda e: {"flagged_questions": [
                            {"context_id": 1, "severity": "critical", "category": "x", "issue": ""},
                            {"context_id": 2, "severity": "critical", "category": "y", "issue": ""},
                        ]})
    result = prefill_bank(2, model_config=None)
    assert result["success"] is False
    assert get_bank_stats()["total_contexts"] == 0


def test_prefill_excludes_context_with_both_critical_and_warning(monkeypatch):
    """A context with critical+warning is excluded, not demoted to warned."""
    import tools.reading_question_bank as rqb
    from tools.reading_question_bank import init_db, prefill_bank, get_bank_stats

    init_db()
    exam = _exam([_ctx(i + 1, " ".join(["mot"] * 100) + f" d{i}") for i in range(2)])
    monkeypatch.setattr(rqb, "_generate_reading_exam",
                        lambda n, model_config, avoid_topics=None: exam)
    monkeypatch.setattr(rqb, "_review_reading_exam", lambda e: {
        "flagged_questions": [
            {"context_id": 1, "severity": "critical", "category": "x", "issue": ""},
            {"context_id": 1, "severity": "warning",  "category": "y", "issue": ""},
        ]
    })
    result = prefill_bank(2, model_config=None)
    assert result["success"] is True
    stats = get_bank_stats()
    assert stats["total_contexts"] == 1   # ctx 1 excluded, not demoted to warned
    assert stats["warned"] == 0
    assert stats["reviewed"] == 1
