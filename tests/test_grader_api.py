# tests/test_grader_api.py
"""Tests for grader/app.py — Flask API endpoints."""

import json
import sqlite3
import uuid
from datetime import datetime

import pytest


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db_path(tmp_path):
    """Provide a temporary database path and patch DB_PATH in both modules."""
    path = str(tmp_path / "test_grader_api.db")
    import tools.question_bank as qb
    import tools.grader_db as gdb
    old_qb, old_gdb = qb.DB_PATH, gdb.DB_PATH
    qb.DB_PATH = path
    gdb.DB_PATH = path
    yield path
    qb.DB_PATH = old_qb
    gdb.DB_PATH = old_gdb


@pytest.fixture
def client(db_path):
    """Create a Flask test client backed by the temporary database."""
    from grader.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ── Helpers ───────────────────────────────────────────────────────────────────

def _seed_contexts(db_path: str, count: int) -> list:
    """
    Initialise the DB and insert `count` test contexts.
    Also ensures the reviews table exists so seeds work independently.
    Returns a list of context_id strings.
    """
    from tools.question_bank import init_db
    from tools.grader_db import init_reviews_table
    init_db()
    init_reviews_table()

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


# ── Task 6: GET /api/contexts ─────────────────────────────────────────────────

def test_get_contexts_returns_all(client, db_path):
    """GET /api/contexts with no filters returns all seeded contexts."""
    context_ids = _seed_contexts(db_path, 3)

    response = client.get("/api/contexts")
    assert response.status_code == 200

    data = response.get_json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    returned_ids = {item["context_id"] for item in data["items"]}
    assert returned_ids == set(context_ids)


def test_get_contexts_filter_by_status(client, db_path):
    """GET /api/contexts?status=battle_tested returns only matching contexts."""
    context_ids = _seed_contexts(db_path, 3)

    # Promote first context to battle_tested
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE contexts SET status = 'battle_tested' WHERE context_id = ?",
        (context_ids[0],),
    )
    conn.commit()
    conn.close()

    response = client.get("/api/contexts?status=battle_tested")
    assert response.status_code == 200
    data = response.get_json()
    assert data["total"] == 1
    assert data["items"][0]["context_id"] == context_ids[0]

    response2 = client.get("/api/contexts?status=reviewed")
    data2 = response2.get_json()
    assert data2["total"] == 2


def test_get_contexts_empty_bank(client, db_path):
    """GET /api/contexts returns total=0 when question bank is empty."""
    _seed_contexts(db_path, 0)  # initialise DB with no contexts

    response = client.get("/api/contexts")
    assert response.status_code == 200
    data = response.get_json()
    assert data["total"] == 0
    assert data["items"] == []


# ── Task 7: GET /api/contexts/<id> and PUT /api/contexts/<id>/review ──────────

def test_get_context_detail_no_review(client, db_path):
    """GET /api/contexts/<id> returns context_data with review=null when no review exists."""
    context_ids = _seed_contexts(db_path, 1)
    cid = context_ids[0]

    response = client.get(f"/api/contexts/{cid}")
    assert response.status_code == 200

    data = response.get_json()
    assert data["context_id"] == cid
    assert data["context_data"] is not None
    assert data["context_data"]["context_id"] == cid
    assert data["review"] is None


def test_get_context_detail_with_review(client, db_path):
    """GET /api/contexts/<id> shows review data after a PUT review is submitted."""
    context_ids = _seed_contexts(db_path, 1)
    cid = context_ids[0]

    # Submit a review first
    put_resp = client.put(
        f"/api/contexts/{cid}/review",
        json={"expert_rating": "Good", "expert_critique": "Looks fine."},
    )
    assert put_resp.status_code == 200

    # Now fetch detail
    get_resp = client.get(f"/api/contexts/{cid}")
    assert get_resp.status_code == 200
    data = get_resp.get_json()

    assert data["review"] is not None
    review = data["review"]
    assert review["expert_rating"] == "Good"
    assert review["expert_critique"] == "Looks fine."
    assert review["snapshot_outdated"] is False
    assert "model_output" in review
    assert "llm_evaluator_rating" in review
    assert "llm_evaluator_critique" in review
    assert "agreement" in review


def test_get_context_detail_404(client, db_path):
    """GET /api/contexts/<unknown_id> returns 404."""
    _seed_contexts(db_path, 0)

    response = client.get("/api/contexts/does-not-exist")
    assert response.status_code == 404


def test_put_review_creates_new(client, db_path):
    """PUT /api/contexts/<id>/review creates a new review and returns success."""
    context_ids = _seed_contexts(db_path, 1)
    cid = context_ids[0]

    response = client.put(
        f"/api/contexts/{cid}/review",
        json={"expert_rating": "Good", "expert_critique": "Clear and correct."},
    )
    assert response.status_code == 200

    data = response.get_json()
    assert data["success"] is True
    assert "updated_at" in data


def test_put_review_updates_existing(client, db_path):
    """PUT /api/contexts/<id>/review updates an existing review's rating."""
    context_ids = _seed_contexts(db_path, 1)
    cid = context_ids[0]

    # Create initial review
    client.put(
        f"/api/contexts/{cid}/review",
        json={"expert_rating": "Good", "expert_critique": "Initially good."},
    )

    # Update it
    response = client.put(
        f"/api/contexts/{cid}/review",
        json={"expert_rating": "Bad", "expert_critique": "Found issues."},
    )
    assert response.status_code == 200

    # Verify via detail endpoint
    detail = client.get(f"/api/contexts/{cid}").get_json()
    assert detail["review"]["expert_rating"] == "Bad"
    assert detail["review"]["expert_critique"] == "Found issues."


def test_put_review_invalid_rating(client, db_path):
    """PUT /api/contexts/<id>/review with rating='Maybe' returns 400."""
    context_ids = _seed_contexts(db_path, 1)
    cid = context_ids[0]

    response = client.put(
        f"/api/contexts/{cid}/review",
        json={"expert_rating": "Maybe"},
    )
    assert response.status_code == 400


def test_put_review_missing_rating(client, db_path):
    """PUT /api/contexts/<id>/review with no expert_rating field returns 400."""
    context_ids = _seed_contexts(db_path, 1)
    cid = context_ids[0]

    response = client.put(
        f"/api/contexts/{cid}/review",
        json={"expert_critique": "No rating provided."},
    )
    assert response.status_code == 400


def test_put_review_404_unknown_context(client, db_path):
    """PUT /api/contexts/<unknown>/review returns 404 for non-existent context."""
    _seed_contexts(db_path, 0)

    response = client.put(
        "/api/contexts/no-such-id/review",
        json={"expert_rating": "Good", "expert_critique": ""},
    )
    assert response.status_code == 404