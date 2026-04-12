"""Integration tests for grader Flask API."""
import json
import sqlite3
import pytest

@pytest.fixture
def db_path(tmp_path):
    """Provide a temporary database path and patch DB_PATH in both modules."""
    path = str(tmp_path / "test_question_bank.db")
    import tools.question_bank as qb
    import tools.grader_db as gdb
    qb.DB_PATH = path
    gdb.DB_PATH = path
    return path


@pytest.fixture
def client(db_path):
    """Create a Flask test client with a fresh database."""
    from grader.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def _seed_contexts(db_path, count=3):
    """Insert test contexts. Returns list of context_ids."""
    from tools.question_bank import init_db
    from tools.grader_db import init_reviews_table
    init_db()
    init_reviews_table()
    conn = sqlite3.connect(db_path)
    ids = []
    for i in range(count):
        ctx_id = f"ctx-{i:04d}"
        ctx_type = "fill_in_blank" if i % 2 == 0 else "error_identification"
        q_json = json.dumps([{
            "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
            "correct_answer": "A",
            "grammar_topic": "preposition",
            "explanation": {"why_correct": "Reason", "grammar_rule": "Rule"},
        }])
        conn.execute(
            "INSERT INTO contexts VALUES (?, ?, ?, ?, 1, 'preposition', 'reviewed', 's', '2026-04-12T00:00:00', 0, ?, 0, 0)",
            (ctx_id, ctx_type, f"Passage {i} with (1) _______________ blank.", q_json, f"hash-{i}"),
        )
        ids.append(ctx_id)
    conn.commit()
    conn.close()
    return ids


# ── GET /api/contexts ─────────────────────────────────────────────────────────

def test_get_contexts_returns_all(client, db_path):
    """GET /api/contexts returns all contexts with total count."""
    _seed_contexts(db_path, 3)
    resp = client.get("/api/contexts")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 3
    assert len(data["items"]) == 3


def test_get_contexts_filter_by_status(client, db_path):
    """GET /api/contexts?status=reviewed filters correctly."""
    ids = _seed_contexts(db_path, 3)
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE contexts SET status = 'battle_tested' WHERE context_id = ?", (ids[0],))
    conn.commit()
    conn.close()

    resp = client.get("/api/contexts?status=battle_tested")
    data = resp.get_json()
    assert data["total"] == 1


def test_get_contexts_empty_bank(client, db_path):
    """GET /api/contexts returns empty list when bank has no contexts."""
    from tools.question_bank import init_db
    from tools.grader_db import init_reviews_table
    init_db()
    init_reviews_table()

    resp = client.get("/api/contexts")
    data = resp.get_json()
    assert data["total"] == 0
    assert data["items"] == []
