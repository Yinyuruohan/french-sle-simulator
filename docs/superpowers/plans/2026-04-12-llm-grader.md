# LLM Grader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Flask web application for subject-matter experts to review AI-generated exam content, rate contexts as Good/Bad, and annotate with free-text critiques.

**Architecture:** Flask backend serves a REST API (`/api/*`) and static SPA files. A new `tools/grader_db.py` module manages the `reviews` table in the shared `question_bank.db`. The SPA is vanilla HTML/CSS/JS with hash-based routing — no build step. The grader reads from the existing `contexts` table (never writes to it) and writes only to the `reviews` table.

**Tech Stack:** Python, Flask, SQLite, vanilla HTML/CSS/JS

**Spec:** `docs/superpowers/specs/2026-04-11-llm-grader-design.md`

---

## File Structure

**New files:**
- `tools/grader_db.py` — Reviews table: init, CRUD, filtered queries. One clear responsibility: all `reviews` table operations.
- `tests/test_grader_db.py` — Unit tests for `tools/grader_db.py`
- `tests/test_grader_api.py` — Integration tests for Flask API endpoints
- `grader/app.py` — Flask app: REST API endpoints + static file serving
- `grader/static/index.html` — SPA entry point (list + detail views, hash-based routing)
- `grader/static/style.css` — Grader styles (Plus Jakarta Sans, blue palette from simulator)
- `grader/static/app.js` — Vanilla JS: API calls, view rendering, state management

**Modified files:**
- `requirements.txt` — Add `flask>=3.0.0`

---

### Task 1: Add Flask dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add flask to requirements.txt**

Add `flask>=3.0.0` under the SLE Exam Simulator section:

```
# SLE Exam Simulator
openai>=1.0.0
streamlit>=1.40.0
flask>=3.0.0
```

- [ ] **Step 2: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: Flask installs successfully, no conflicts.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add flask dependency for grader app"
```

---

### Task 2: Data layer — `init_reviews_table` and `cleanup_empty_reviews`

**Files:**
- Create: `tools/grader_db.py`
- Create: `tests/test_grader_db.py`

- [ ] **Step 1: Write failing tests for table init and cleanup**

Create `tests/test_grader_db.py`:

```python
"""Tests for tools/grader_db.py"""
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


def _seed_contexts(db_path, count=3):
    """Insert test contexts into the contexts table. Returns list of context_ids."""
    from tools.question_bank import init_db
    init_db()
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


# ── init_reviews_table ────────────────────────────────────────────────────────

def test_init_reviews_table_creates_table(db_path):
    """init_reviews_table creates the reviews table with expected columns."""
    from tools.question_bank import init_db
    from tools.grader_db import init_reviews_table
    init_db()
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
    from tools.question_bank import init_db
    from tools.grader_db import init_reviews_table
    init_db()
    init_reviews_table()
    init_reviews_table()


# ── cleanup_empty_reviews ─────────────────────────────────────────────────────

def test_cleanup_empty_reviews_deletes_unrated(db_path):
    """cleanup_empty_reviews deletes reviews where expert_rating IS NULL."""
    from tools.question_bank import init_db
    from tools.grader_db import init_reviews_table, cleanup_empty_reviews
    init_db()
    init_reviews_table()

    conn = sqlite3.connect(db_path)
    # Insert one rated and one unrated review
    conn.execute(
        "INSERT INTO reviews (context_id, model_output, expert_rating, expert_critique, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("ctx-rated", '{}', "Good", "Nice", "2026-04-12T00:00:00", "2026-04-12T00:00:00"),
    )
    conn.execute(
        "INSERT INTO reviews (context_id, model_output, created_at, updated_at) VALUES (?, ?, ?, ?)",
        ("ctx-unrated", '{}', "2026-04-12T00:00:00", "2026-04-12T00:00:00"),
    )
    conn.commit()
    conn.close()

    deleted = cleanup_empty_reviews()
    assert deleted == 1

    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT context_id FROM reviews").fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0][0] == "ctx-rated"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_grader_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.grader_db'`

- [ ] **Step 3: Write minimal implementation**

Create `tools/grader_db.py`:

```python
"""
LLM Grader — Reviews Data Layer

Manages the `reviews` table in the shared question_bank.db.
Read-only access to the `contexts` table for snapshots and filtering.
Never writes to the `contexts` table.
"""

import hashlib
import json
import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "question_bank.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_reviews_table():
    """Create the reviews table if it doesn't exist."""
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                context_id TEXT PRIMARY KEY,
                model_output TEXT NOT NULL,
                expert_rating TEXT,
                expert_critique TEXT,
                llm_evaluator_rating TEXT,
                llm_evaluator_critique TEXT,
                agreement INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()


def cleanup_empty_reviews() -> int:
    """Delete review records where expert_rating IS NULL (viewed but never rated).
    Returns the number of deleted rows."""
    conn = _get_conn()
    try:
        cursor = conn.execute("DELETE FROM reviews WHERE expert_rating IS NULL")
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_grader_db.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/grader_db.py tests/test_grader_db.py
git commit -m "feat(grader): add reviews table init and cleanup"
```

---

### Task 3: Data layer — `get_contexts_for_review`

**Files:**
- Modify: `tools/grader_db.py`
- Modify: `tests/test_grader_db.py`

- [ ] **Step 1: Write failing tests for filtered context listing**

Append to `tests/test_grader_db.py`:

```python
# ── get_contexts_for_review ───────────────────────────────────────────────────

def test_get_contexts_for_review_returns_all(db_path):
    """get_contexts_for_review with no filters returns all contexts."""
    from tools.grader_db import init_reviews_table, get_contexts_for_review
    ids = _seed_contexts(db_path, 3)
    init_reviews_table()
    result = get_contexts_for_review({})
    assert result["total"] == 3
    assert len(result["items"]) == 3
    # Each item has required fields
    item = result["items"][0]
    assert "context_id" in item
    assert "status" in item
    assert "user_flags" in item
    assert "expert_rating" in item


def test_get_contexts_for_review_filter_status(db_path):
    """get_contexts_for_review filters by status."""
    from tools.grader_db import init_reviews_table, get_contexts_for_review
    ids = _seed_contexts(db_path, 3)
    init_reviews_table()
    # Change one context to battle_tested
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE contexts SET status = 'battle_tested' WHERE context_id = ?", (ids[0],))
    conn.commit()
    conn.close()

    result = get_contexts_for_review({"status": "battle_tested"})
    assert result["total"] == 1
    assert result["items"][0]["context_id"] == ids[0]


def test_get_contexts_for_review_filter_flagged(db_path):
    """get_contexts_for_review filters by flagged status."""
    from tools.grader_db import init_reviews_table, get_contexts_for_review
    ids = _seed_contexts(db_path, 3)
    init_reviews_table()
    # Flag one context
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE contexts SET user_flags = 2 WHERE context_id = ?", (ids[1],))
    conn.commit()
    conn.close()

    flagged = get_contexts_for_review({"flagged": "true"})
    assert flagged["total"] == 1
    assert flagged["items"][0]["context_id"] == ids[1]

    unflagged = get_contexts_for_review({"flagged": "false"})
    assert unflagged["total"] == 2


def test_get_contexts_for_review_filter_reviewed(db_path):
    """get_contexts_for_review filters by whether an expert review exists."""
    from tools.grader_db import init_reviews_table, get_contexts_for_review
    ids = _seed_contexts(db_path, 3)
    init_reviews_table()
    # Create a review for one context
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO reviews (context_id, model_output, expert_rating, created_at, updated_at) VALUES (?, '{}', 'Good', '2026-04-12', '2026-04-12')",
        (ids[0],),
    )
    conn.commit()
    conn.close()

    reviewed = get_contexts_for_review({"reviewed": "true"})
    assert reviewed["total"] == 1

    not_reviewed = get_contexts_for_review({"reviewed": "false"})
    assert not_reviewed["total"] == 2


def test_get_contexts_for_review_combined_filters(db_path):
    """get_contexts_for_review combines multiple filters with AND logic."""
    from tools.grader_db import init_reviews_table, get_contexts_for_review
    ids = _seed_contexts(db_path, 3)
    init_reviews_table()
    # Flag ctx-0 and add a review for it
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE contexts SET user_flags = 1 WHERE context_id = ?", (ids[0],))
    conn.execute(
        "INSERT INTO reviews (context_id, model_output, expert_rating, created_at, updated_at) VALUES (?, '{}', 'Bad', '2026-04-12', '2026-04-12')",
        (ids[0],),
    )
    conn.commit()
    conn.close()

    result = get_contexts_for_review({"flagged": "true", "reviewed": "true"})
    assert result["total"] == 1
    assert result["items"][0]["context_id"] == ids[0]
    assert result["items"][0]["expert_rating"] == "Bad"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_grader_db.py::test_get_contexts_for_review_returns_all -v`
Expected: FAIL — `ImportError: cannot import name 'get_contexts_for_review'`

- [ ] **Step 3: Write implementation**

Add to `tools/grader_db.py`:

```python
def get_contexts_for_review(filters: dict) -> dict:
    """Query contexts with optional filters, left-joined with reviews.

    Args:
        filters: dict with optional keys:
            - status: 'battle_tested', 'reviewed', or 'warned'
            - flagged: 'true' (user_flags >= 1) or 'false' (user_flags == 0)
            - reviewed: 'true' (has expert review) or 'false' (no review)

    Returns:
        {"total": int, "items": [{"context_id", "status", "user_flags", "expert_rating"}, ...]}
    """
    conn = _get_conn()
    try:
        sql = """
            SELECT c.context_id, c.status, c.user_flags, r.expert_rating
            FROM contexts c
            LEFT JOIN reviews r ON c.context_id = r.context_id
            WHERE 1=1
        """
        params = []

        if "status" in filters:
            sql += " AND c.status = ?"
            params.append(filters["status"])

        if "flagged" in filters:
            if filters["flagged"] == "true":
                sql += " AND c.user_flags >= 1"
            elif filters["flagged"] == "false":
                sql += " AND c.user_flags = 0"

        if "reviewed" in filters:
            if filters["reviewed"] == "true":
                sql += " AND r.expert_rating IS NOT NULL"
            elif filters["reviewed"] == "false":
                sql += " AND r.context_id IS NULL"

        sql += " ORDER BY c.created_at DESC"

        rows = conn.execute(sql, params).fetchall()
        items = [
            {
                "context_id": row["context_id"],
                "status": row["status"],
                "user_flags": row["user_flags"],
                "expert_rating": row["expert_rating"],
            }
            for row in rows
        ]
        return {"total": len(items), "items": items}
    finally:
        conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_grader_db.py -v`
Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/grader_db.py tests/test_grader_db.py
git commit -m "feat(grader): add filtered context listing for review"
```

---

### Task 4: Data layer — `get_review`, `save_review`

**Files:**
- Modify: `tools/grader_db.py`
- Modify: `tests/test_grader_db.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_grader_db.py`:

```python
# ── get_review ────────────────────────────────────────────────────────────────

def test_get_review_returns_none_when_missing(db_path):
    """get_review returns None when no review exists for a context."""
    from tools.grader_db import init_reviews_table, get_review
    _seed_contexts(db_path, 1)
    init_reviews_table()
    assert get_review("ctx-0000") is None


def test_get_review_returns_existing_review(db_path):
    """get_review returns the full review dict when one exists."""
    from tools.grader_db import init_reviews_table, get_review
    _seed_contexts(db_path, 1)
    init_reviews_table()
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO reviews (context_id, model_output, expert_rating, expert_critique, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("ctx-0000", '{"passage": "test"}', "Good", "Looks fine", "2026-04-12T00:00:00", "2026-04-12T01:00:00"),
    )
    conn.commit()
    conn.close()

    review = get_review("ctx-0000")
    assert review is not None
    assert review["context_id"] == "ctx-0000"
    assert review["expert_rating"] == "Good"
    assert review["expert_critique"] == "Looks fine"
    assert json.loads(review["model_output"])["passage"] == "test"


# ── save_review ───────────────────────────────────────────────────────────────

def test_save_review_creates_snapshot_on_first_save(db_path):
    """save_review creates review record with model_output snapshot on first call."""
    from tools.grader_db import init_reviews_table, save_review, get_review
    ids = _seed_contexts(db_path, 1)
    init_reviews_table()

    result = save_review(ids[0], "Good", "Nice question")
    assert "updated_at" in result

    review = get_review(ids[0])
    assert review["expert_rating"] == "Good"
    assert review["expert_critique"] == "Nice question"
    # model_output should contain the snapshotted context data
    snapshot = json.loads(review["model_output"])
    assert snapshot["context_id"] == ids[0]
    assert snapshot["type"] == "fill_in_blank"
    assert "passage" in snapshot
    assert "questions" in snapshot


def test_save_review_updates_existing_review(db_path):
    """save_review updates an existing review without changing the snapshot."""
    from tools.grader_db import init_reviews_table, save_review, get_review
    ids = _seed_contexts(db_path, 1)
    init_reviews_table()

    save_review(ids[0], "Good", "First impression")
    original_snapshot = get_review(ids[0])["model_output"]

    save_review(ids[0], "Bad", "Changed my mind")
    updated = get_review(ids[0])
    assert updated["expert_rating"] == "Bad"
    assert updated["expert_critique"] == "Changed my mind"
    # Snapshot unchanged
    assert updated["model_output"] == original_snapshot


def test_save_review_without_critique(db_path):
    """save_review works with empty critique."""
    from tools.grader_db import init_reviews_table, save_review, get_review
    ids = _seed_contexts(db_path, 1)
    init_reviews_table()

    save_review(ids[0], "Good", "")
    review = get_review(ids[0])
    assert review["expert_rating"] == "Good"
    assert review["expert_critique"] == ""


def test_save_review_returns_none_for_missing_context(db_path):
    """save_review returns None if context_id doesn't exist in contexts table."""
    from tools.grader_db import init_reviews_table, save_review
    _seed_contexts(db_path, 0)
    init_reviews_table()

    result = save_review("nonexistent-id", "Good", "")
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_grader_db.py::test_get_review_returns_none_when_missing -v`
Expected: FAIL — `ImportError: cannot import name 'get_review'`

- [ ] **Step 3: Write implementation**

Add to `tools/grader_db.py`:

```python
def _snapshot_context(conn: sqlite3.Connection, context_id: str) -> str | None:
    """Build a JSON snapshot of a context from the contexts table.
    Returns JSON string or None if context doesn't exist."""
    row = conn.execute(
        "SELECT context_id, type, passage, questions_json, grammar_topics, status FROM contexts WHERE context_id = ?",
        (context_id,),
    ).fetchone()
    if not row:
        return None
    return json.dumps({
        "context_id": row["context_id"],
        "type": row["type"],
        "passage": row["passage"],
        "questions": json.loads(row["questions_json"]),
        "grammar_topics": row["grammar_topics"],
        "status": row["status"],
    }, ensure_ascii=False)


def get_review(context_id: str) -> dict | None:
    """Fetch existing review. Returns review dict or None."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM reviews WHERE context_id = ?", (context_id,)
        ).fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        conn.close()


def save_review(context_id: str, expert_rating: str, expert_critique: str) -> dict | None:
    """Upsert expert rating and critique. Creates the review record (with snapshot)
    if one doesn't exist yet. Returns {"updated_at": ...} or None if context not found."""
    conn = _get_conn()
    try:
        now = datetime.now().isoformat()

        # Check if review already exists
        existing = conn.execute(
            "SELECT 1 FROM reviews WHERE context_id = ?", (context_id,)
        ).fetchone()

        if existing:
            # Update existing review
            conn.execute(
                "UPDATE reviews SET expert_rating = ?, expert_critique = ?, updated_at = ? WHERE context_id = ?",
                (expert_rating, expert_critique, now, context_id),
            )
        else:
            # Create new review with snapshot
            snapshot = _snapshot_context(conn, context_id)
            if snapshot is None:
                return None
            conn.execute(
                """INSERT INTO reviews
                   (context_id, model_output, expert_rating, expert_critique, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (context_id, snapshot, expert_rating, expert_critique, now, now),
            )

        conn.commit()
        return {"updated_at": now}
    finally:
        conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_grader_db.py -v`
Expected: All 15 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/grader_db.py tests/test_grader_db.py
git commit -m "feat(grader): add get_review and save_review with snapshot creation"
```

---

### Task 5: Data layer — snapshot staleness detection

**Files:**
- Modify: `tools/grader_db.py`
- Modify: `tests/test_grader_db.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_grader_db.py`:

```python
# ── snapshot staleness ────────────────────────────────────────────────────────

def test_is_snapshot_outdated_returns_false_when_unchanged(db_path):
    """is_snapshot_outdated returns False when context hasn't changed."""
    from tools.grader_db import init_reviews_table, save_review, is_snapshot_outdated
    ids = _seed_contexts(db_path, 1)
    init_reviews_table()
    save_review(ids[0], "Good", "")

    assert is_snapshot_outdated(ids[0]) is False


def test_is_snapshot_outdated_returns_true_when_passage_changed(db_path):
    """is_snapshot_outdated returns True when context passage has changed."""
    from tools.grader_db import init_reviews_table, save_review, is_snapshot_outdated
    ids = _seed_contexts(db_path, 1)
    init_reviews_table()
    save_review(ids[0], "Good", "")

    # Modify the context passage after snapshot
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE contexts SET passage = 'Modified passage' WHERE context_id = ?", (ids[0],))
    conn.commit()
    conn.close()

    assert is_snapshot_outdated(ids[0]) is True


def test_is_snapshot_outdated_returns_none_when_no_review(db_path):
    """is_snapshot_outdated returns None when no review exists."""
    from tools.grader_db import init_reviews_table, is_snapshot_outdated
    _seed_contexts(db_path, 1)
    init_reviews_table()

    assert is_snapshot_outdated("ctx-0000") is None


def test_is_snapshot_outdated_returns_none_when_context_deleted(db_path):
    """is_snapshot_outdated returns None when context no longer exists in bank."""
    from tools.grader_db import init_reviews_table, save_review, is_snapshot_outdated
    ids = _seed_contexts(db_path, 1)
    init_reviews_table()
    save_review(ids[0], "Good", "")

    # Delete the context
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM contexts WHERE context_id = ?", (ids[0],))
    conn.commit()
    conn.close()

    assert is_snapshot_outdated(ids[0]) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_grader_db.py::test_is_snapshot_outdated_returns_false_when_unchanged -v`
Expected: FAIL — `ImportError: cannot import name 'is_snapshot_outdated'`

- [ ] **Step 3: Write implementation**

Add to `tools/grader_db.py`:

```python
def _context_data_hash(context_data: dict) -> str:
    """SHA-256 hash of the relevant context fields for staleness comparison."""
    normalized = json.dumps({
        "passage": context_data.get("passage", ""),
        "questions": context_data.get("questions", []),
        "grammar_topics": context_data.get("grammar_topics", ""),
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def is_snapshot_outdated(context_id: str) -> bool | None:
    """Check if the review snapshot differs from the current context data.

    Returns:
        False if snapshot matches current context.
        True if snapshot differs from current context.
        None if no review exists or context has been deleted.
    """
    conn = _get_conn()
    try:
        # Get the snapshot
        review_row = conn.execute(
            "SELECT model_output FROM reviews WHERE context_id = ?", (context_id,)
        ).fetchone()
        if not review_row:
            return None

        # Get the current context
        current_snapshot = _snapshot_context(conn, context_id)
        if current_snapshot is None:
            return None  # context deleted — review stands alone

        snapshot_hash = _context_data_hash(json.loads(review_row["model_output"]))
        current_hash = _context_data_hash(json.loads(current_snapshot))
        return snapshot_hash != current_hash
    finally:
        conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_grader_db.py -v`
Expected: All 19 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/grader_db.py tests/test_grader_db.py
git commit -m "feat(grader): add snapshot staleness detection"
```

---

### Task 6: Flask API — app setup and `GET /api/contexts`

**Files:**
- Create: `grader/app.py`
- Create: `tests/test_grader_api.py`

- [ ] **Step 1: Write failing tests for the contexts list endpoint**

Create `tests/test_grader_api.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_grader_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'grader'`

- [ ] **Step 3: Write Flask app with `create_app` factory and contexts endpoint**

Create `grader/__init__.py` (empty file) and `grader/app.py`:

```python
"""
LLM Grader — Flask Application

REST API for expert review of AI-generated exam content.
Serves static SPA files and API endpoints under /api/*.
"""

import argparse
import os
import sys

from flask import Flask, jsonify, request, send_from_directory

# Ensure tools/ is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tools.grader_db import (
    init_reviews_table,
    cleanup_empty_reviews,
    get_contexts_for_review,
)


def create_app() -> Flask:
    """Flask application factory."""
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app = Flask(__name__, static_folder=static_dir)

    # Initialize database on startup
    init_reviews_table()
    cleanup_empty_reviews()

    # ── Static SPA serving ────────────────────────────────────────────────

    @app.route("/")
    def index():
        return send_from_directory(static_dir, "index.html")

    @app.route("/<path:filename>")
    def static_files(filename):
        return send_from_directory(static_dir, filename)

    # ── API: List contexts ────────────────────────────────────────────────

    @app.get("/api/contexts")
    def api_list_contexts():
        filters = {}
        for key in ("status", "flagged", "reviewed"):
            val = request.args.get(key)
            if val is not None:
                filters[key] = val
        return jsonify(get_contexts_for_review(filters))

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LLM Grader server")
    parser.add_argument("--port", type=int, default=int(os.environ.get("GRADER_PORT", 5001)))
    args = parser.parse_args()

    app = create_app()
    app.run(port=args.port, debug=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_grader_api.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add grader/__init__.py grader/app.py tests/test_grader_api.py
git commit -m "feat(grader): Flask app with GET /api/contexts endpoint"
```

---

### Task 7: Flask API — `GET /api/contexts/{id}` and `PUT /api/contexts/{id}/review`

**Files:**
- Modify: `grader/app.py`
- Modify: `tests/test_grader_api.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_grader_api.py`:

```python
# ── GET /api/contexts/{id} ────────────────────────────────────────────────────

def test_get_context_detail_no_review(client, db_path):
    """GET /api/contexts/{id} returns context data with review=null when no review exists."""
    ids = _seed_contexts(db_path, 1)
    resp = client.get(f"/api/contexts/{ids[0]}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["context_id"] == ids[0]
    assert data["context_data"] is not None
    assert data["context_data"]["type"] == "fill_in_blank"
    assert data["review"] is None


def test_get_context_detail_with_review(client, db_path):
    """GET /api/contexts/{id} returns existing review with snapshot_outdated flag."""
    ids = _seed_contexts(db_path, 1)
    # Submit a review first
    client.put(f"/api/contexts/{ids[0]}/review",
               json={"expert_rating": "Good", "expert_critique": "Nice"})

    resp = client.get(f"/api/contexts/{ids[0]}")
    data = resp.get_json()
    assert data["review"] is not None
    assert data["review"]["expert_rating"] == "Good"
    assert data["review"]["snapshot_outdated"] is False


def test_get_context_detail_404(client, db_path):
    """GET /api/contexts/{id} returns 404 for unknown context."""
    from tools.question_bank import init_db
    from tools.grader_db import init_reviews_table
    init_db()
    init_reviews_table()

    resp = client.get("/api/contexts/nonexistent")
    assert resp.status_code == 404


# ── PUT /api/contexts/{id}/review ─────────────────────────────────────────────

def test_put_review_creates_new(client, db_path):
    """PUT /api/contexts/{id}/review creates a new review."""
    ids = _seed_contexts(db_path, 1)
    resp = client.put(f"/api/contexts/{ids[0]}/review",
                      json={"expert_rating": "Good", "expert_critique": "Looks correct"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "updated_at" in data


def test_put_review_updates_existing(client, db_path):
    """PUT /api/contexts/{id}/review updates an existing review."""
    ids = _seed_contexts(db_path, 1)
    client.put(f"/api/contexts/{ids[0]}/review",
               json={"expert_rating": "Good", "expert_critique": ""})
    resp = client.put(f"/api/contexts/{ids[0]}/review",
                      json={"expert_rating": "Bad", "expert_critique": "Actually wrong"})
    assert resp.status_code == 200

    detail = client.get(f"/api/contexts/{ids[0]}").get_json()
    assert detail["review"]["expert_rating"] == "Bad"


def test_put_review_invalid_rating(client, db_path):
    """PUT /api/contexts/{id}/review returns 400 for invalid rating."""
    ids = _seed_contexts(db_path, 1)
    resp = client.put(f"/api/contexts/{ids[0]}/review",
                      json={"expert_rating": "Maybe", "expert_critique": ""})
    assert resp.status_code == 400


def test_put_review_missing_rating(client, db_path):
    """PUT /api/contexts/{id}/review returns 400 when expert_rating is missing."""
    ids = _seed_contexts(db_path, 1)
    resp = client.put(f"/api/contexts/{ids[0]}/review",
                      json={"expert_critique": "no rating"})
    assert resp.status_code == 400


def test_put_review_404_unknown_context(client, db_path):
    """PUT /api/contexts/{id}/review returns 404 for unknown context."""
    from tools.question_bank import init_db
    from tools.grader_db import init_reviews_table
    init_db()
    init_reviews_table()

    resp = client.put("/api/contexts/nonexistent/review",
                      json={"expert_rating": "Good", "expert_critique": ""})
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_grader_api.py::test_get_context_detail_no_review -v`
Expected: FAIL — 404 (route not yet defined)

- [ ] **Step 3: Write implementation**

Add to `create_app()` in `grader/app.py`, after the existing `/api/contexts` route. Also add imports for `get_review`, `save_review`, `is_snapshot_outdated`:

Update the import block at the top:

```python
from tools.grader_db import (
    init_reviews_table,
    cleanup_empty_reviews,
    get_contexts_for_review,
    get_review,
    save_review,
    is_snapshot_outdated,
)
```

Add endpoints inside `create_app()`:

```python
    # ── API: Context detail ───────────────────────────────────────────────

    @app.get("/api/contexts/<context_id>")
    def api_context_detail(context_id):
        # Read live context data from contexts table
        from tools.grader_db import _snapshot_context, _get_conn
        import json as _json
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT context_id, type, passage, questions_json, grammar_topics, status "
                "FROM contexts WHERE context_id = ?",
                (context_id,),
            ).fetchone()
        finally:
            conn.close()

        if not row:
            return jsonify({"error": "Context not found"}), 404

        context_data = {
            "context_id": row["context_id"],
            "type": row["type"],
            "passage": row["passage"],
            "questions": _json.loads(row["questions_json"]),
            "grammar_topics": row["grammar_topics"],
            "status": row["status"],
        }

        review = get_review(context_id)
        review_data = None
        if review:
            outdated = is_snapshot_outdated(context_id)
            review_data = {
                "model_output": _json.loads(review["model_output"]),
                "expert_rating": review["expert_rating"],
                "expert_critique": review["expert_critique"],
                "llm_evaluator_rating": review["llm_evaluator_rating"],
                "llm_evaluator_critique": review["llm_evaluator_critique"],
                "agreement": review["agreement"],
                "snapshot_outdated": outdated if outdated is not None else False,
            }

        return jsonify({
            "context_id": context_id,
            "context_data": context_data,
            "review": review_data,
        })

    # ── API: Submit/update review ─────────────────────────────────────────

    @app.put("/api/contexts/<context_id>/review")
    def api_put_review(context_id):
        body = request.get_json(silent=True) or {}
        rating = body.get("expert_rating")
        critique = body.get("expert_critique", "")

        if rating not in ("Good", "Bad"):
            return jsonify({"error": "expert_rating must be 'Good' or 'Bad'"}), 400

        result = save_review(context_id, rating, critique)
        if result is None:
            return jsonify({"error": "Context not found"}), 404

        return jsonify({"success": True, **result})
```

Note: The detail endpoint reads directly from the contexts table rather than going through `_snapshot_context` to avoid creating a snapshot — the spec says GET does not create a review record. Refactor the direct SQL into a helper function `get_context_data` in `grader_db.py` to keep Flask from writing SQL directly:

Add to `tools/grader_db.py`:

```python
def get_context_data(context_id: str) -> dict | None:
    """Read live context data from the contexts table. Returns dict or None."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT context_id, type, passage, questions_json, grammar_topics, status "
            "FROM contexts WHERE context_id = ?",
            (context_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "context_id": row["context_id"],
            "type": row["type"],
            "passage": row["passage"],
            "questions": json.loads(row["questions_json"]),
            "grammar_topics": row["grammar_topics"],
            "status": row["status"],
        }
    finally:
        conn.close()
```

Then simplify the detail endpoint in `grader/app.py` to use it:

```python
    @app.get("/api/contexts/<context_id>")
    def api_context_detail(context_id):
        context_data = get_context_data(context_id)
        if not context_data:
            return jsonify({"error": "Context not found"}), 404

        review = get_review(context_id)
        review_data = None
        if review:
            outdated = is_snapshot_outdated(context_id)
            review_data = {
                "model_output": json.loads(review["model_output"]),
                "expert_rating": review["expert_rating"],
                "expert_critique": review["expert_critique"],
                "llm_evaluator_rating": review["llm_evaluator_rating"],
                "llm_evaluator_critique": review["llm_evaluator_critique"],
                "agreement": review["agreement"],
                "snapshot_outdated": outdated if outdated is not None else False,
            }

        return jsonify({
            "context_id": context_id,
            "context_data": context_data,
            "review": review_data,
        })
```

Add `import json` and `get_context_data` to the import block in `grader/app.py`:

```python
import json

from tools.grader_db import (
    init_reviews_table,
    cleanup_empty_reviews,
    get_contexts_for_review,
    get_context_data,
    get_review,
    save_review,
    is_snapshot_outdated,
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_grader_api.py -v`
Expected: All 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add grader/app.py tools/grader_db.py tests/test_grader_api.py
git commit -m "feat(grader): add context detail and review submission endpoints"
```

---

### Task 8: Frontend — SPA skeleton and list view

**Files:**
- Create: `grader/static/index.html`
- Create: `grader/static/style.css`
- Create: `grader/static/app.js`

- [ ] **Step 1: Create index.html**

Create `grader/static/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LLM Grader — Expert Review</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div id="app">
        <header>
            <h1>LLM Grader</h1>
            <p class="subtitle">Expert Review Interface</p>
        </header>
        <main id="main"></main>
    </div>
    <div id="toast" class="toast hidden"></div>
    <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create style.css**

Create `grader/static/style.css` with the design system matching the simulator:

```css
/* ── Reset & Base ─────────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body {
    font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
    background: #f0f6ff;
    color: #334155;
    font-size: 14px;
    line-height: 1.65;
}

#app {
    max-width: 1200px;
    margin: 0 auto;
    padding: 24px 32px;
}

/* ── Header ───────────────────────────────────────────────────────────────── */
header { margin-bottom: 24px; }
header h1 {
    font-size: 28px;
    font-weight: 800;
    color: #0f172a;
    letter-spacing: -0.02em;
}
.subtitle {
    font-size: 14px;
    color: #64748b;
    margin-top: 2px;
}

/* ── Filters ──────────────────────────────────────────────────────────────── */
.filters {
    display: flex;
    gap: 12px;
    margin-bottom: 16px;
    align-items: center;
}
.filters label {
    font-size: 12px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}
.filters select {
    font-family: inherit;
    font-size: 13px;
    padding: 6px 10px;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    background: white;
    color: #334155;
    cursor: pointer;
}

/* ── Table ─────────────────────────────────────────────────────────────────── */
.ctx-table {
    width: 100%;
    border-collapse: collapse;
    background: white;
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.ctx-table th {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    color: #64748b;
    letter-spacing: 0.04em;
    padding: 12px 16px;
    text-align: left;
    border-bottom: 2px solid #e2e8f0;
    background: #f8fafc;
}
.ctx-table td {
    padding: 10px 16px;
    border-bottom: 1px solid #f1f5f9;
    font-size: 13px;
}
.ctx-table tr:last-child td { border-bottom: none; }
.ctx-table tbody tr {
    cursor: pointer;
    transition: background 0.15s;
}
.ctx-table tbody tr:hover { background: #f0f6ff; }

.ctx-id { font-family: monospace; font-size: 12px; color: #475569; }

/* ── Badges ────────────────────────────────────────────────────────────────── */
.badge {
    display: inline-block;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 4px;
}
.badge-battle_tested { background: #dcfce7; color: #166534; }
.badge-reviewed { background: #dbeafe; color: #1e40af; }
.badge-warned { background: #fef9c3; color: #854d0e; }
.badge-good { background: #dcfce7; color: #166534; }
.badge-bad { background: #fee2e2; color: #991b1b; }
.badge-none { color: #94a3b8; font-style: italic; font-weight: 400; }

.flags-red { color: #dc2626; font-weight: 600; }

/* ── Detail view layout ───────────────────────────────────────────────────── */
.detail-layout {
    display: grid;
    grid-template-columns: 180px 1fr 340px;
    gap: 16px;
}

/* ── Sidebar navigator ────────────────────────────────────────────────────── */
.sidebar {
    position: sticky;
    top: 20px;
    align-self: start;
    background: white;
    border-radius: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    overflow: hidden;
}
.sidebar-header {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    color: #64748b;
    padding: 10px 12px;
    border-bottom: 2px solid #e2e8f0;
    background: #f8fafc;
    letter-spacing: 0.04em;
}
.sidebar-list {
    max-height: 520px;
    overflow-y: auto;
}
.sidebar-item {
    padding: 7px 10px;
    border-bottom: 1px solid #f1f5f9;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: background 0.15s;
    font-size: 11px;
    color: #475569;
}
.sidebar-item:hover { background: #f0f6ff; }
.sidebar-item.active {
    background: #dbeafe;
    border-left: 3px solid #2563eb;
    color: #1e40af;
    font-weight: 600;
}

.dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
}
.dot-reviewed { background: #16a34a; }
.dot-empty { border: 2px solid #cbd5e1; box-sizing: border-box; }

/* ── Navigation bar ───────────────────────────────────────────────────────── */
.nav-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
}
.nav-counter { font-size: 13px; color: #64748b; }

/* ── Cards ─────────────────────────────────────────────────────────────────── */
.card {
    background: white;
    border-radius: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    overflow: hidden;
    margin-bottom: 12px;
}
.card-header {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    color: #64748b;
    padding: 10px 16px;
    border-bottom: 1px solid #e2e8f0;
    background: #f8fafc;
    letter-spacing: 0.04em;
}
.card-body { padding: 16px; }

/* ── Passage ───────────────────────────────────────────────────────────────── */
.passage { font-size: 13px; line-height: 1.7; color: #1e293b; }

/* ── Question options ──────────────────────────────────────────────────────── */
.options-grid {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 6px 8px;
    font-size: 13px;
    margin-bottom: 12px;
}
.option-label { font-weight: 600; color: #64748b; }
.option-correct .option-label {
    color: #166534;
    background: #dcfce7;
    padding: 0 4px;
    border-radius: 3px;
}
.option-correct .option-text { color: #166534; font-weight: 600; }

.meta-label {
    font-size: 11px;
    text-transform: uppercase;
    color: #64748b;
    font-weight: 600;
    margin-bottom: 4px;
}
.meta-value { font-size: 13px; color: #334155; line-height: 1.6; }

/* ── Review panel ──────────────────────────────────────────────────────────── */
.rating-buttons {
    display: flex;
    gap: 8px;
    margin-bottom: 16px;
}
.rating-btn {
    flex: 1;
    text-align: center;
    padding: 10px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    border: 2px solid #e2e8f0;
    background: white;
    color: #94a3b8;
    transition: all 0.15s;
}
.rating-btn:hover { border-color: #94a3b8; }
.rating-btn.selected-good {
    background: #dcfce7;
    color: #166534;
    border-color: #16a34a;
}
.rating-btn.selected-bad {
    background: #fee2e2;
    color: #991b1b;
    border-color: #dc2626;
}

.critique-textarea {
    width: 100%;
    min-height: 100px;
    font-family: inherit;
    font-size: 13px;
    padding: 10px 12px;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    resize: vertical;
    color: #334155;
    margin-bottom: 16px;
}
.critique-textarea:focus {
    outline: none;
    border-color: #2563eb;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.1);
}

.btn-primary {
    display: inline-block;
    background: #2563eb;
    color: white;
    padding: 10px 24px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    border: none;
    font-family: inherit;
    box-shadow: 0 2px 8px rgba(37,99,235,0.2);
    transition: background 0.15s;
}
.btn-primary:hover { background: #1d4ed8; }
.btn-primary:disabled { background: #94a3b8; cursor: not-allowed; box-shadow: none; }

.btn-nav {
    font-family: inherit;
    font-size: 13px;
    padding: 6px 16px;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    background: white;
    color: #334155;
    cursor: pointer;
    transition: background 0.15s;
}
.btn-nav:hover { background: #f0f6ff; }
.btn-nav:disabled { color: #cbd5e1; cursor: not-allowed; }

.back-link {
    display: block;
    text-align: center;
    font-size: 13px;
    color: #2563eb;
    cursor: pointer;
    font-weight: 500;
    margin-top: 12px;
}
.back-link:hover { text-decoration: underline; }

/* ── Snapshot outdated banner ──────────────────────────────────────────────── */
.banner-outdated {
    background: #fef9c3;
    color: #854d0e;
    font-size: 12px;
    font-weight: 500;
    padding: 8px 16px;
    border-radius: 6px;
    margin-bottom: 12px;
}

/* ── Toast ─────────────────────────────────────────────────────────────────── */
.toast {
    position: fixed;
    bottom: 24px;
    right: 24px;
    padding: 10px 20px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    color: white;
    z-index: 1000;
    transition: opacity 0.3s;
}
.toast.hidden { opacity: 0; pointer-events: none; }
.toast.success { background: #16a34a; }
.toast.error { background: #dc2626; }

/* ── LLM Evaluator placeholder ─────────────────────────────────────────────── */
.placeholder-text {
    text-align: center;
    padding: 20px;
    color: #94a3b8;
    font-size: 13px;
    font-style: italic;
}
```

- [ ] **Step 3: Create app.js with state management and list view**

Create `grader/static/app.js`:

```javascript
/* LLM Grader — SPA */
(function () {
  "use strict";

  // ── State ──────────────────────────────────────────────────────────────
  const state = {
    filters: JSON.parse(sessionStorage.getItem("grader_filters") || "{}"),
    contextList: [], // {context_id, status, user_flags, expert_rating}[]
    currentContextId: null,
  };

  function persistFilters() {
    sessionStorage.setItem("grader_filters", JSON.stringify(state.filters));
  }

  // ── API helpers ────────────────────────────────────────────────────────
  async function api(path, opts = {}) {
    const resp = await fetch(`/api${path}`, {
      headers: { "Content-Type": "application/json" },
      ...opts,
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || `HTTP ${resp.status}`);
    return data;
  }

  function queryString(filters) {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(filters)) {
      if (v) params.set(k, v);
    }
    const qs = params.toString();
    return qs ? `?${qs}` : "";
  }

  // ── Toast ──────────────────────────────────────────────────────────────
  function showToast(msg, type = "success") {
    const el = document.getElementById("toast");
    el.textContent = msg;
    el.className = `toast ${type}`;
    setTimeout(() => el.classList.add("hidden"), 2500);
  }

  // ── Router ─────────────────────────────────────────────────────────────
  function route() {
    const hash = location.hash || "#/";
    const match = hash.match(/^#\/review\/(.+)$/);
    if (match) {
      renderDetailView(match[1]);
    } else {
      renderListView();
    }
  }

  // ── List View ──────────────────────────────────────────────────────────
  async function renderListView() {
    state.currentContextId = null;
    const main = document.getElementById("main");

    try {
      const data = await api(`/contexts${queryString(state.filters)}`);
      state.contextList = data.items;

      main.innerHTML = `
        <div class="filters">
          <div>
            <label>Status</label>
            <select id="f-status">
              <option value="">All</option>
              <option value="battle_tested">Battle Tested</option>
              <option value="reviewed">Reviewed</option>
              <option value="warned">Warned</option>
            </select>
          </div>
          <div>
            <label>Flags</label>
            <select id="f-flagged">
              <option value="">All</option>
              <option value="true">Flagged</option>
              <option value="false">Unflagged</option>
            </select>
          </div>
          <div>
            <label>Reviewed</label>
            <select id="f-reviewed">
              <option value="">All</option>
              <option value="true">Reviewed</option>
              <option value="false">Not Reviewed</option>
            </select>
          </div>
        </div>

        <table class="ctx-table">
          <thead>
            <tr>
              <th>Context ID</th>
              <th>Status</th>
              <th>Flags</th>
              <th>Review</th>
            </tr>
          </thead>
          <tbody id="ctx-tbody"></tbody>
        </table>
      `;

      // Set filter values
      const setVal = (id, key) => {
        const el = document.getElementById(id);
        el.value = state.filters[key] || "";
        el.addEventListener("change", () => {
          state.filters[key] = el.value || undefined;
          if (!el.value) delete state.filters[key];
          persistFilters();
          renderListView();
        });
      };
      setVal("f-status", "status");
      setVal("f-flagged", "flagged");
      setVal("f-reviewed", "reviewed");

      // Render rows
      const tbody = document.getElementById("ctx-tbody");
      for (const item of data.items) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><span class="ctx-id">${item.context_id.slice(0, 8)}</span></td>
          <td><span class="badge badge-${item.status}">${item.status.replace("_", " ")}</span></td>
          <td>${item.user_flags > 0 ? `<span class="flags-red">${item.user_flags}</span>` : "0"}</td>
          <td>${item.expert_rating
            ? `<span class="badge badge-${item.expert_rating.toLowerCase()}">${item.expert_rating}</span>`
            : `<span class="badge-none">not reviewed</span>`}</td>
        `;
        tr.addEventListener("click", () => {
          location.hash = `#/review/${item.context_id}`;
        });
        tbody.appendChild(tr);
      }
    } catch (err) {
      main.innerHTML = `<p style="color:#dc2626">Error loading contexts: ${err.message}</p>`;
    }
  }

  // ── Detail View (placeholder — implemented in Task 9) ──────────────────
  async function renderDetailView(contextId) {
    state.currentContextId = contextId;
    const main = document.getElementById("main");
    main.innerHTML = `<p>Loading...</p>`;

    // If contextList is empty (direct URL access), fetch unfiltered list
    if (state.contextList.length === 0) {
      try {
        const data = await api("/contexts");
        state.contextList = data.items;
      } catch (err) {
        main.innerHTML = `<p style="color:#dc2626">Error: ${err.message}</p>`;
        return;
      }
    }

    try {
      const detail = await api(`/contexts/${contextId}`);
      const idx = state.contextList.findIndex((c) => c.context_id === contextId);
      const total = state.contextList.length;
      const prevId = idx > 0 ? state.contextList[idx - 1].context_id : null;
      const nextId = idx < total - 1 ? state.contextList[idx + 1].context_id : null;

      // Determine sidebar label for each context
      const typeCounters = { fill_in_blank: 0, error_identification: 0 };

      main.innerHTML = buildDetailHTML(detail, idx, total, prevId, nextId);
      bindDetailEvents(detail, prevId, nextId);
      renderSidebar(contextId);
    } catch (err) {
      main.innerHTML = `<p style="color:#dc2626">Error: ${err.message}</p>`;
    }
  }

  function sidebarLabel(item, typeCounters) {
    // We need type info — it's not in the list response,
    // so we use a sequential index instead
    return item.context_id.slice(0, 8);
  }

  function buildDetailHTML(detail, idx, total, prevId, nextId) {
    const ctx = detail.context_data;
    const review = detail.review;
    const rating = review ? review.expert_rating : null;
    const critique = review ? review.expert_critique || "" : "";
    const outdated = review && review.snapshot_outdated;

    let questionsHTML = "";
    for (let i = 0; i < ctx.questions.length; i++) {
      const q = ctx.questions[i];
      let optionsHTML = "";
      for (const [letter, text] of Object.entries(q.options)) {
        const isCorrect = letter === q.correct_answer;
        optionsHTML += `
          <div class="${isCorrect ? "option-correct" : ""}">
            <span class="option-label">${letter}.</span>
            <span class="option-text">${text}${isCorrect ? " \u2713" : ""}</span>
          </div>`;
      }

      questionsHTML += `
        <div class="card">
          <div class="card-header">Question (${i + 1})</div>
          <div class="card-body">
            <div class="options-grid">${optionsHTML}</div>
            <div style="border-top:1px solid #e2e8f0;padding-top:12px;">
              <div class="meta-label">Grammar Topic</div>
              <div class="meta-value">${q.grammar_topic}</div>
            </div>
          </div>
        </div>`;

      if (q.explanation) {
        questionsHTML += `
          <div class="card">
            <div class="card-header">Explanation</div>
            <div class="card-body">
              <div style="margin-bottom:10px;">
                <div class="meta-label">Why Correct</div>
                <div class="meta-value">${q.explanation.why_correct || ""}</div>
              </div>
              <div>
                <div class="meta-label">Grammar Rule</div>
                <div class="meta-value">${q.explanation.grammar_rule || ""}</div>
              </div>
            </div>
          </div>`;
      }
    }

    const llmSection = review && review.llm_evaluator_rating
      ? `<div><div class="meta-label">Rating</div><div class="meta-value">${review.llm_evaluator_rating}</div></div>
         <div><div class="meta-label">Critique</div><div class="meta-value">${review.llm_evaluator_critique}</div></div>`
      : `<div class="placeholder-text">Not yet evaluated</div>`;

    return `
      ${outdated ? '<div class="banner-outdated">Snapshot outdated — the context has been regenerated since this review was created.</div>' : ""}

      <div class="nav-bar">
        <button class="btn-nav" id="btn-prev" ${!prevId ? "disabled" : ""}>&#8592; Previous</button>
        <span class="nav-counter">${idx + 1} of ${total}</span>
        <button class="btn-nav" id="btn-next" ${!nextId ? "disabled" : ""}>Next &#8594;</button>
      </div>

      <div class="detail-layout">
        <div class="sidebar" id="sidebar">
          <div class="sidebar-header">Contexts</div>
          <div class="sidebar-list" id="sidebar-list"></div>
        </div>

        <div class="detail-content">
          <div class="card">
            <div class="card-header">Context Passage &mdash; ${ctx.type.replace("_", " ")} &middot; ${ctx.grammar_topics}</div>
            <div class="card-body">
              <div class="passage">${ctx.passage}</div>
            </div>
          </div>
          ${questionsHTML}
        </div>

        <div class="review-panel">
          <div class="card">
            <div class="card-header">Expert Review</div>
            <div class="card-body">
              <div class="meta-label">Rating</div>
              <div class="rating-buttons">
                <button class="rating-btn ${rating === "Good" ? "selected-good" : ""}" data-rating="Good">Good</button>
                <button class="rating-btn ${rating === "Bad" ? "selected-bad" : ""}" data-rating="Bad">Bad</button>
              </div>
              <div class="meta-label">Critique</div>
              <textarea class="critique-textarea" id="critique" placeholder="Optional \u2014 add notes about this context...">${critique}</textarea>
              <div style="text-align:right;">
                <button class="btn-primary" id="btn-submit">${review ? "Update Review" : "Submit Review"}</button>
              </div>
            </div>
          </div>

          <div class="card">
            <div class="card-header">LLM Evaluator (automated)</div>
            <div class="card-body">${llmSection}</div>
          </div>

          <a class="back-link" id="btn-back">&#8592; Back to list</a>
        </div>
      </div>
    `;
  }

  function bindDetailEvents(detail, prevId, nextId) {
    const contextId = detail.context_id;
    let selectedRating = detail.review ? detail.review.expert_rating : null;

    // Rating buttons
    document.querySelectorAll(".rating-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        selectedRating = btn.dataset.rating;
        document.querySelectorAll(".rating-btn").forEach((b) => {
          b.className = "rating-btn";
        });
        btn.classList.add(selectedRating === "Good" ? "selected-good" : "selected-bad");
      });
    });

    // Submit
    document.getElementById("btn-submit").addEventListener("click", async () => {
      if (!selectedRating) {
        showToast("Please select Good or Bad", "error");
        return;
      }
      const critique = document.getElementById("critique").value;
      const submitBtn = document.getElementById("btn-submit");
      submitBtn.disabled = true;

      // Optimistic sidebar update
      const sidebarItem = document.querySelector(`.sidebar-item[data-id="${contextId}"] .dot`);
      const wasDotClass = sidebarItem ? sidebarItem.className : null;
      if (sidebarItem) {
        sidebarItem.className = "dot dot-reviewed";
      }

      try {
        await api(`/contexts/${contextId}/review`, {
          method: "PUT",
          body: JSON.stringify({
            expert_rating: selectedRating,
            expert_critique: critique,
          }),
        });
        // Update cached list
        const cached = state.contextList.find((c) => c.context_id === contextId);
        if (cached) cached.expert_rating = selectedRating;

        showToast("Review saved");
        submitBtn.textContent = "Update Review";
      } catch (err) {
        // Revert sidebar dot on failure
        if (sidebarItem && wasDotClass) sidebarItem.className = wasDotClass;
        showToast(`Error: ${err.message}`, "error");
      } finally {
        submitBtn.disabled = false;
      }
    });

    // Navigation
    if (prevId) {
      document.getElementById("btn-prev").addEventListener("click", () => {
        location.hash = `#/review/${prevId}`;
      });
    }
    if (nextId) {
      document.getElementById("btn-next").addEventListener("click", () => {
        location.hash = `#/review/${nextId}`;
      });
    }
    document.getElementById("btn-back").addEventListener("click", (e) => {
      e.preventDefault();
      location.hash = "#/";
    });
  }

  function renderSidebar(activeId) {
    const list = document.getElementById("sidebar-list");
    if (!list) return;
    list.innerHTML = "";

    // Type counters for labels
    const counters = { fill_in_blank: 0, error_identification: 0 };

    for (const item of state.contextList) {
      const isActive = item.context_id === activeId;
      const hasReview = !!item.expert_rating;
      const div = document.createElement("div");
      div.className = `sidebar-item${isActive ? " active" : ""}`;
      div.dataset.id = item.context_id;
      div.innerHTML = `
        <span class="dot ${hasReview ? "dot-reviewed" : "dot-empty"}"></span>
        <span>${item.context_id.slice(0, 8)}</span>
      `;
      div.addEventListener("click", () => {
        location.hash = `#/review/${item.context_id}`;
      });
      list.appendChild(div);
    }
  }

  // ── Init ───────────────────────────────────────────────────────────────
  window.addEventListener("hashchange", route);
  route();
})();
```

Note: The sidebar labels use truncated context IDs initially. The spec says to show descriptive labels like "Fill-in #3" / "Error-ID #7", but the list endpoint doesn't include type information. We'll add type to the list response in a follow-up step.

- [ ] **Step 4: Verify the app loads in the browser**

Run: `cd c:/Users/zhuol/Project/french_sle_simulator && python grader/app.py`
Open: `http://localhost:5001` in a browser.
Expected: The list view renders with filters and table (may be empty if no contexts in bank).

- [ ] **Step 5: Commit**

```bash
git add grader/static/index.html grader/static/style.css grader/static/app.js
git commit -m "feat(grader): SPA frontend with list view and detail view"
```

---

### Task 9: Add `type` to list response for sidebar labels

**Files:**
- Modify: `tools/grader_db.py` — `get_contexts_for_review` query
- Modify: `tests/test_grader_db.py`
- Modify: `grader/static/app.js` — sidebar label rendering

- [ ] **Step 1: Write failing test**

Append to `tests/test_grader_db.py`:

```python
def test_get_contexts_for_review_includes_type(db_path):
    """get_contexts_for_review items include context type."""
    from tools.grader_db import init_reviews_table, get_contexts_for_review
    _seed_contexts(db_path, 3)
    init_reviews_table()
    result = get_contexts_for_review({})
    for item in result["items"]:
        assert "type" in item
        assert item["type"] in ("fill_in_blank", "error_identification")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_grader_db.py::test_get_contexts_for_review_includes_type -v`
Expected: FAIL — `KeyError: 'type'`

- [ ] **Step 3: Update query and response**

In `tools/grader_db.py`, update `get_contexts_for_review`:

Change the SELECT clause from:
```python
        sql = """
            SELECT c.context_id, c.status, c.user_flags, r.expert_rating
```
to:
```python
        sql = """
            SELECT c.context_id, c.type, c.status, c.user_flags, r.expert_rating
```

And update the items list comprehension to include `"type": row["type"]`.

- [ ] **Step 4: Update sidebar labels in app.js**

In `grader/static/app.js`, update the `renderSidebar` function to use descriptive labels:

```javascript
  function renderSidebar(activeId) {
    const list = document.getElementById("sidebar-list");
    if (!list) return;
    list.innerHTML = "";

    const counters = { fill_in_blank: 0, error_identification: 0 };

    for (const item of state.contextList) {
      const type = item.type || "fill_in_blank";
      counters[type] = (counters[type] || 0) + 1;
      const label = type === "error_identification"
        ? `Error-ID #${counters[type]}`
        : `Fill-in #${counters[type]}`;

      const isActive = item.context_id === activeId;
      const hasReview = !!item.expert_rating;
      const div = document.createElement("div");
      div.className = `sidebar-item${isActive ? " active" : ""}`;
      div.dataset.id = item.context_id;
      div.innerHTML = `
        <span class="dot ${hasReview ? "dot-reviewed" : "dot-empty"}"></span>
        <span>${label}</span>
      `;
      div.addEventListener("click", () => {
        location.hash = `#/review/${item.context_id}`;
      });
      list.appendChild(div);
    }
  }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_grader_db.py tests/test_grader_api.py -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/grader_db.py tests/test_grader_db.py grader/static/app.js
git commit -m "feat(grader): add context type to list response and sidebar labels"
```

---

### Task 10: Manual integration test

**Files:** None (verification only)

- [ ] **Step 1: Ensure the question bank has some contexts**

Run: `python -c "from tools.question_bank import init_db, get_bank_stats; init_db(); print(get_bank_stats())"`

If the bank is empty, you'll need some contexts to test with. Use the Streamlit app to generate an exam, or use prefill_bank (requires API key).

- [ ] **Step 2: Start the grader**

Run: `python grader/app.py`
Expected: Flask starts on port 5001 with no errors.

- [ ] **Step 3: Test list view**

Open `http://localhost:5001` in a browser.
Verify:
- Contexts appear in the table with correct status badges
- Filters work (change Status dropdown, see rows filter)
- Clicking a row navigates to detail view

- [ ] **Step 4: Test detail view**

Verify:
- Passage displays correctly
- Questions show with correct answer highlighted green
- Sidebar shows context labels with review indicator dots
- Navigation (Prev/Next) works
- Clicking sidebar items loads different contexts

- [ ] **Step 5: Test review submission**

Verify:
- Click "Good" → button highlights green
- Click "Bad" → button highlights red
- Type text in critique field
- Click "Submit Review" → toast shows "Review saved"
- Sidebar dot turns green
- Navigate away and back → review persists
- Click "Update Review" to change rating → works

- [ ] **Step 6: Test direct URL access**

Navigate directly to `http://localhost:5001/#/review/<context_id>` (use a context_id from the list).
Verify: sidebar populates and context loads without error.

- [ ] **Step 7: Run full test suite**

Run: `pytest tests/test_grader_db.py tests/test_grader_api.py -v`
Expected: All tests PASS.

---

### Task 11: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add grader to file structure and key entry points**

Add to the `Key entry points` section:
```
- `python grader/app.py` — launches the LLM Grader expert review interface
```

Add to the `File Structure` section:
```
grader/
  app.py                  # Flask app: REST API + static file serving for expert review
  static/
    index.html            # SPA entry point (list + detail views, hash-based routing)
    style.css             # Grader styles (Plus Jakarta Sans, blue palette)
    app.js                # Vanilla JS: API calls, view rendering, state management
tools/
  ...
  grader_db.py            # Reviews table: init, CRUD, filtered queries
tests/
  ...
  test_grader_db.py       # Unit tests for grader_db.py
  test_grader_api.py      # Integration tests for grader Flask API
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add grader to CLAUDE.md file structure and entry points"
```