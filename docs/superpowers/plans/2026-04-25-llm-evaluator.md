# LLM Evaluator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an on-demand LLM evaluator button to the LLM Grader detail view that calls DeepSeek (or any configured model) via the judge prompt and saves the rating + critique in-place.

**Architecture:** A new `tools/llm_evaluator.py` module calls the LLM and parses its response; `grader_db.save_llm_review()` writes the result to the reviews table (inserting a snapshot row if needed); a new Flask endpoint wires the two together; and `app.js` renders a 3-state card (not-yet / loading / done) with an in-place DOM update.

**Tech Stack:** Python 3.10+, OpenAI SDK, Flask, SQLite, vanilla JS (no build step)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `tools/llm_evaluator.py` | **Create** | Read judge prompt, serialize context, call LLM, parse response |
| `tests/test_llm_evaluator.py` | **Create** | Unit tests for `evaluate_context()` |
| `tools/grader_db.py` | **Modify** | Add `save_llm_review()`; fix `cleanup_empty_reviews()` |
| `tests/test_grader_db.py` | **Modify** | Tests for `save_llm_review()` and the cleanup fix |
| `grader/app.py` | **Modify** | Add `POST /api/contexts/<id>/llm-review`; update `create_app()` |
| `tests/test_grader_api.py` | **Modify** | Tests for the new endpoint |
| `grader/static/app.js` | **Modify** | 3-state LLM evaluator card + click handler |
| `.env.template` | **Modify** | Add `EVALUATOR_*` vars |

---

## Task 1 — `tools/llm_evaluator.py`

**Files:**
- Create: `tools/llm_evaluator.py`
- Create: `tests/test_llm_evaluator.py`

- [ ] **Step 1.1 — Write the failing tests**

Create `tests/test_llm_evaluator.py`:

```python
# tests/test_llm_evaluator.py
"""Tests for tools/llm_evaluator.py"""
from unittest.mock import MagicMock, patch

import pytest


SAMPLE_CONTEXT = {
    "context_id": "test-123",
    "type": "fill_in_blank",
    "passage": "Le ministère _______________ une nouvelle politique.",
    "questions": [
        {
            "options": {"A": "adopte", "B": "adoptez", "C": "adoptent", "D": "adoptais"},
            "correct_answer": "A",
            "grammar_topic": "conjugation",
            "explanation": {
                "why_correct": "Le sujet est 'Le ministère' (3e personne du singulier).",
                "grammar_rule": "Le verbe s'accorde avec le sujet en personne et en nombre.",
            },
        }
    ],
    "grammar_topics": "conjugation",
    "status": "reviewed",
}


@pytest.fixture
def model_config():
    from tools.model_config import ModelConfig
    return ModelConfig(model="test-model", base_url="https://test.api", api_key="test-key")


@patch("tools.llm_evaluator.OpenAI")
def test_evaluate_context_good(mock_openai, model_config):
    """Returns {"rating": "Good", "critique": "..."} for a Good LLM response."""
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(
            content="**Rating:** Good\n\n**Commentary:** The question correctly tests verb conjugation."
        ))]
    )

    from tools.llm_evaluator import evaluate_context
    result = evaluate_context(SAMPLE_CONTEXT, model_config)

    assert result["rating"] == "Good"
    assert len(result["critique"]) > 0


@patch("tools.llm_evaluator.OpenAI")
def test_evaluate_context_bad(mock_openai, model_config):
    """Returns {"rating": "Bad", "critique": "..."} for a Bad LLM response."""
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(
            content="**Rating:** Bad\n\n**Commentary:** The distractor 'adoptez' is implausible."
        ))]
    )

    from tools.llm_evaluator import evaluate_context
    result = evaluate_context(SAMPLE_CONTEXT, model_config)

    assert result["rating"] == "Bad"
    assert len(result["critique"]) > 0


@patch("tools.llm_evaluator.OpenAI")
def test_evaluate_context_malformed_raises(mock_openai, model_config):
    """Raises ValueError when LLM response contains no Rating line."""
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="I cannot evaluate this."))]
    )

    from tools.llm_evaluator import evaluate_context
    with pytest.raises(ValueError, match="Malformed LLM response"):
        evaluate_context(SAMPLE_CONTEXT, model_config)


@patch("tools.llm_evaluator.OpenAI")
def test_evaluate_context_passes_judge_prompt_as_system(mock_openai, model_config):
    """System message contains content from LLM_judge_prompt.md."""
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="**Rating:** Good\n\n**Commentary:** OK."))]
    )

    from tools.llm_evaluator import evaluate_context
    evaluate_context(SAMPLE_CONTEXT, model_config)

    call_kwargs = mock_client.chat.completions.create.call_args[1]
    messages = call_kwargs["messages"]
    system_msg = next((m for m in messages if m["role"] == "system"), None)
    assert system_msg is not None
    assert "EVALUATION CRITERIA" in system_msg["content"]
```

- [ ] **Step 1.2 — Run the tests to confirm they all fail**

```
pytest tests/test_llm_evaluator.py -v
```

Expected: 4 errors — `ModuleNotFoundError: No module named 'tools.llm_evaluator'`

- [ ] **Step 1.3 — Create `tools/llm_evaluator.py`**

```python
"""
LLM Evaluator — calls the LLM judge and parses its rating/critique.
"""

import os
import re

from openai import OpenAI

from tools.model_config import ModelConfig

_JUDGE_PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "LLM_judge_prompt.md"
)


def _read_judge_prompt() -> str:
    with open(_JUDGE_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _serialize_context(context_data: dict) -> str:
    lines = [
        f"Type: {context_data['type']}",
        f"Grammar topics: {context_data['grammar_topics']}",
        f"\nPassage:\n{context_data['passage']}",
    ]
    for i, q in enumerate(context_data["questions"], 1):
        lines.append(f"\nQuestion {i}:")
        for letter, text in q["options"].items():
            lines.append(f"  {letter}: {text}")
        lines.append(f"Correct answer: {q['correct_answer']}")
        lines.append(f"Grammar topic: {q['grammar_topic']}")
        if "explanation" in q:
            lines.append(f"Why correct: {q['explanation']['why_correct']}")
            lines.append(f"Grammar rule: {q['explanation']['grammar_rule']}")
    return "\n".join(lines)


def _parse_response(text: str) -> dict:
    rating_match = re.search(
        r"\*{0,2}Rating:?\*{0,2}\s*(Good|Bad)", text, re.IGNORECASE
    )
    if not rating_match:
        raise ValueError(
            f"Malformed LLM response: no Rating found. Response: {text[:200]!r}"
        )
    rating = rating_match.group(1).capitalize()

    commentary_match = re.search(
        r"\*{0,2}Commentary:?\*{0,2}\s*(.+)", text, re.IGNORECASE | re.DOTALL
    )
    critique = commentary_match.group(1).strip() if commentary_match else ""

    return {"rating": rating, "critique": critique}


def evaluate_context(context_data: dict, model_config: ModelConfig) -> dict:
    """
    Call the LLM judge and return {"rating": "Good"|"Bad", "critique": "..."}.

    Raises ValueError if the LLM response is malformed (no Rating line).
    """
    system_prompt = _read_judge_prompt()
    user_message = _serialize_context(context_data)

    client = OpenAI(api_key=model_config.api_key, base_url=model_config.base_url)
    response = client.chat.completions.create(
        model=model_config.model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.1,
        max_tokens=512,
    )

    text = response.choices[0].message.content
    return _parse_response(text)
```

- [ ] **Step 1.4 — Run the tests to confirm they all pass**

```
pytest tests/test_llm_evaluator.py -v
```

Expected: 4 PASSED

- [ ] **Step 1.5 — Commit**

```bash
git add tools/llm_evaluator.py tests/test_llm_evaluator.py
git commit -m "feat: add tools/llm_evaluator.py with evaluate_context()"
```

---

## Task 2 — `tools/grader_db.py`: add `save_llm_review()` + fix `cleanup_empty_reviews()`

**Files:**
- Modify: `tools/grader_db.py`
- Modify: `tests/test_grader_db.py`

**Note:** `cleanup_empty_reviews()` currently deletes any review row where `expert_rating IS NULL`. This will incorrectly delete LLM-only rows (inserted by `save_llm_review()` before any expert review). The fix adds `AND llm_evaluator_rating IS NULL` to the DELETE condition.

- [ ] **Step 2.1 — Write the failing tests**

Append the following four test functions to `tests/test_grader_db.py` (after the last existing test):

```python
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
```

- [ ] **Step 2.2 — Run the new tests to confirm they fail**

```
pytest tests/test_grader_db.py::test_save_llm_review_insert tests/test_grader_db.py::test_save_llm_review_update_existing_row tests/test_grader_db.py::test_save_llm_review_returns_none_for_missing_context tests/test_grader_db.py::test_cleanup_empty_reviews_preserves_llm_only_rows -v
```

Expected: 4 failures — `AttributeError: module 'tools.grader_db' has no attribute 'save_llm_review'` (first 3) and FAIL on the cleanup test.

- [ ] **Step 2.3 — Add `save_llm_review()` to `tools/grader_db.py`**

Add at the top of the file, update the existing import block:

```python
from typing import Optional
```

Add `save_llm_review` after the existing `save_review` function (before the `# ── Task 5` comment):

```python
def save_llm_review(
    context_id: str, llm_rating: str, llm_critique: str
) -> Optional[dict]:
    """
    Create or update the LLM evaluator fields for the given context_id.

    If a review row exists: UPDATE llm_evaluator_rating, llm_evaluator_critique, updated_at only.
    If no row exists: INSERT a new row with a context snapshot; expert_rating and agreement left NULL.

    Returns {"updated_at": <iso string>} or None if context_id not in contexts table.
    """
    now = datetime.now().isoformat()

    conn = _get_conn()
    try:
        existing = conn.execute(
            "SELECT context_id FROM reviews WHERE context_id = ?", (context_id,)
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE reviews
                   SET llm_evaluator_rating = ?, llm_evaluator_critique = ?, updated_at = ?
                   WHERE context_id = ?""",
                (llm_rating, llm_critique, now, context_id),
            )
            conn.commit()
            return {"updated_at": now}
        else:
            snapshot = _snapshot_context(conn, context_id)
            if snapshot is None:
                return None

            conn.execute(
                """INSERT INTO reviews
                   (context_id, model_output, expert_rating, expert_critique,
                    llm_evaluator_rating, llm_evaluator_critique, agreement,
                    created_at, updated_at)
                   VALUES (?, ?, NULL, NULL, ?, ?, NULL, ?, ?)""",
                (context_id, snapshot, llm_rating, llm_critique, now, now),
            )
            conn.commit()
            return {"updated_at": now}
    finally:
        conn.close()
```

- [ ] **Step 2.4 — Fix `cleanup_empty_reviews()` in `tools/grader_db.py`**

Find the existing function (lines ~49-57 in the original file) and change the DELETE query:

Old:
```python
cursor = conn.execute("DELETE FROM reviews WHERE expert_rating IS NULL")
```

New:
```python
cursor = conn.execute(
    "DELETE FROM reviews WHERE expert_rating IS NULL AND llm_evaluator_rating IS NULL"
)
```

- [ ] **Step 2.5 — Run all grader_db tests**

```
pytest tests/test_grader_db.py -v
```

Expected: all tests pass (19 existing + 4 new = 23 PASSED)

- [ ] **Step 2.6 — Commit**

```bash
git add tools/grader_db.py tests/test_grader_db.py
git commit -m "feat: add grader_db.save_llm_review(); fix cleanup_empty_reviews to preserve LLM-only rows"
```

---

## Task 3 — `grader/app.py`: new endpoint + updated `create_app()`

**Files:**
- Modify: `grader/app.py`
- Modify: `tests/test_grader_api.py`

- [ ] **Step 3.1 — Write the failing tests**

Append the following to `tests/test_grader_api.py` (after the last existing test):

```python
# ── LLM Evaluator endpoint ────────────────────────────────────────────────────

from unittest.mock import patch


@patch("grader.app.evaluate_context")
def test_post_llm_review_success(mock_eval, client, db_path):
    """POST /api/contexts/<id>/llm-review returns rating, critique, updated_at."""
    context_ids = _seed_contexts(db_path, 1)
    mock_eval.return_value = {"rating": "Good", "critique": "Well done."}

    resp = client.post(f"/api/contexts/{context_ids[0]}/llm-review")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["rating"] == "Good"
    assert data["critique"] == "Well done."
    assert "updated_at" in data


@patch("grader.app.evaluate_context")
def test_post_llm_review_404_for_unknown_context(mock_eval, client, db_path):
    """POST /api/contexts/<id>/llm-review returns 404 for a context not in DB."""
    _seed_contexts(db_path, 0)

    resp = client.post("/api/contexts/does-not-exist/llm-review")

    assert resp.status_code == 404
    mock_eval.assert_not_called()


@patch("grader.app.evaluate_context")
def test_post_llm_review_502_on_malformed_response(mock_eval, client, db_path):
    """POST /api/contexts/<id>/llm-review returns 502 when evaluate_context raises ValueError."""
    context_ids = _seed_contexts(db_path, 1)
    mock_eval.side_effect = ValueError("Malformed LLM response: no Rating found.")

    resp = client.post(f"/api/contexts/{context_ids[0]}/llm-review")

    assert resp.status_code == 502
    assert "error" in resp.get_json()
```

- [ ] **Step 3.2 — Run the new tests to confirm they fail**

```
pytest tests/test_grader_api.py::test_post_llm_review_success tests/test_grader_api.py::test_post_llm_review_404_for_unknown_context tests/test_grader_api.py::test_post_llm_review_502_on_malformed_response -v
```

Expected: 3 failures — 404 for all three (route not registered yet)

- [ ] **Step 3.3 — Update `grader/app.py`**

**3a. Update the import block** — add `save_llm_review` to the grader_db import and add new top-level imports:

```python
import os

from tools.grader_db import (
    cleanup_empty_reviews,
    get_context_data,
    get_contexts_for_review,
    get_review,
    init_reviews_table,
    is_snapshot_outdated,
    save_llm_review,
    save_review,
)
from tools.llm_evaluator import evaluate_context
from tools.model_config import ModelConfig
```

**3b. Add `_load_evaluator_config()` helper** — insert before `create_app()`:

```python
def _load_evaluator_config() -> ModelConfig:
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
    return ModelConfig(
        model=os.getenv("EVALUATOR_MODEL", "deepseek-v4-pro"),
        base_url=os.getenv("EVALUATOR_BASE_URL", "https://api.deepseek.com"),
        api_key=os.getenv("EVALUATOR_API_KEY") or deepseek_key,
    )
```

**3c. Update `create_app()` signature** — change:

Old:
```python
def create_app():
    """Application factory. Initialises DB tables and registers all routes."""
    app = Flask(__name__, static_folder=None)
```

New:
```python
def create_app(evaluator_config: ModelConfig | None = None):
    """Application factory. Initialises DB tables and registers all routes."""
    if evaluator_config is None:
        evaluator_config = _load_evaluator_config()
    app = Flask(__name__, static_folder=None)
```

**3d. Register the new endpoint** — add inside `create_app()`, after the existing `put_review` route and before the `export_excel` route:

```python
    # ── POST /api/contexts/<context_id>/llm-review ────────────────────────────

    @app.route("/api/contexts/<context_id>/llm-review", methods=["POST"])
    def post_llm_review(context_id):
        """Request an LLM evaluation for the given context."""
        context_data = get_context_data(context_id)
        if context_data is None:
            return jsonify({"error": "Context not found"}), 404

        try:
            result = evaluate_context(context_data, evaluator_config)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 502

        saved = save_llm_review(context_id, result["rating"], result["critique"])
        if saved is None:
            return jsonify({"error": "Internal error saving LLM review"}), 500

        return jsonify({
            "rating": result["rating"],
            "critique": result["critique"],
            "updated_at": saved["updated_at"],
        })
```

- [ ] **Step 3.4 — Run all grader API tests**

```
pytest tests/test_grader_api.py -v
```

Expected: all tests pass (11 existing + 3 new = 14 PASSED)

- [ ] **Step 3.5 — Commit**

```bash
git add grader/app.py tests/test_grader_api.py
git commit -m "feat: add POST /api/contexts/<id>/llm-review endpoint"
```

---

## Task 4 — `grader/static/app.js`: 3-state LLM evaluator card

**Files:**
- Modify: `grader/static/app.js`

No automated tests — verify manually by opening the grader UI after Task 5.

- [ ] **Step 4.1 — Add `buildLlmEvaluatorHTML()` helper**

In `app.js`, add this function directly before `buildDetailHTML` (before line 263):

```javascript
  function buildLlmEvaluatorHTML(review) {
    if (review && review.llm_evaluator_rating) {
      const badgeClass =
        review.llm_evaluator_rating === "Good" ? "badge-good" : "badge-bad";
      return `
        <div>
          <div class="meta-label">Rating</div>
          <div class="meta-value">
            <span class="badge ${badgeClass}">${esc(review.llm_evaluator_rating)}</span>
          </div>
        </div>
        <div style="margin-top:10px;">
          <div class="meta-label">Critique</div>
          <div class="meta-value">${esc(review.llm_evaluator_critique || "")}</div>
        </div>
        <div style="margin-top:12px;text-align:right;">
          <button class="btn-primary" id="btn-llm-review">Re-run</button>
        </div>`;
    }
    return `
      <div class="placeholder-text">Not yet evaluated</div>
      <div style="margin-top:12px;text-align:right;">
        <button class="btn-primary" id="btn-llm-review">Request LLM Review</button>
      </div>`;
  }
```

- [ ] **Step 4.2 — Replace the static `llmSection` in `buildDetailHTML()`**

Find (lines 314–317):
```javascript
    const llmSection = review && review.llm_evaluator_rating
      ? `<div><div class="meta-label">Rating</div><div class="meta-value">${esc(review.llm_evaluator_rating)}</div></div>
         <div><div class="meta-label">Critique</div><div class="meta-value">${esc(review.llm_evaluator_critique)}</div></div>`
      : `<div class="placeholder-text">Not yet evaluated</div>`;
```

Delete those 4 lines entirely (the card now calls `buildLlmEvaluatorHTML` directly).

Then find (lines 361–364):
```javascript
          <div class="card">
            <div class="card-header">LLM Evaluator (automated)</div>
            <div class="card-body">${llmSection}</div>
          </div>
```

Replace with:
```javascript
          <div class="card">
            <div class="card-header">LLM Evaluator (automated)</div>
            <div class="card-body" id="llm-evaluator-body">${buildLlmEvaluatorHTML(review)}</div>
          </div>
```

- [ ] **Step 4.3 — Add `bindLlmReviewBtn()` handler**

Add this function directly before `bindDetailEvents` (before line 372):

```javascript
  function bindLlmReviewBtn(contextId) {
    const btn = document.getElementById("btn-llm-review");
    if (!btn) return;
    btn.addEventListener("click", async () => {
      const body = document.getElementById("llm-evaluator-body");
      const originalText = btn.textContent;
      btn.disabled = true;
      btn.textContent = "Évaluation en cours…";
      try {
        const result = await api(`/contexts/${contextId}/llm-review`, {
          method: "POST",
        });
        body.innerHTML = buildLlmEvaluatorHTML({
          llm_evaluator_rating: result.rating,
          llm_evaluator_critique: result.critique,
        });
        bindLlmReviewBtn(contextId);
        showToast("LLM review complete");
      } catch (err) {
        showToast(`Error: ${err.message}`, "error");
        btn.disabled = false;
        btn.textContent = originalText;
      }
    });
  }
```

- [ ] **Step 4.4 — Call `bindLlmReviewBtn()` from `bindDetailEvents()`**

At the end of `bindDetailEvents()`, before the closing `}` (after the `btn-back` listener block), add:

```javascript
    bindLlmReviewBtn(contextId);
```

- [ ] **Step 4.5 — Commit**

```bash
git add grader/static/app.js
git commit -m "feat: add 3-state LLM evaluator card to grader detail view"
```

---

## Task 5 — `.env.template`: add `EVALUATOR_*` vars

**Files:**
- Modify: `.env.template`

- [ ] **Step 5.1 — Add the EVALUATOR block to `.env.template`**

At the end of `.env.template`, append:

```
EVALUATOR_API_KEY=
EVALUATOR_BASE_URL=
EVALUATOR_MODEL=
```

The section header comment should read:

```
# LLM Evaluator (leave blank to fall back to DEEPSEEK_API_KEY + deepseek-v4-pro)
EVALUATOR_API_KEY=
EVALUATOR_BASE_URL=
EVALUATOR_MODEL=
```

Place it after the existing `REVIEW_MODEL=` line, following the same pattern as the other per-tool blocks.

- [ ] **Step 5.2 — Run the full test suite**

```
pytest tests/ -v
```

Expected: all tests pass (6 model_config + 3 generate + 17 question_bank + 23 grader_db + 14 grader_api + 4 llm_evaluator = 67+ PASSED, 0 FAILED)

- [ ] **Step 5.3 — Commit**

```bash
git add .env.template
git commit -m "chore: add EVALUATOR_* vars to .env.template"
```

---

## Manual Smoke Test

After all tasks are committed:

1. Restart the grader: `python grader/app.py`
2. Open `http://localhost:5001`
3. Click any context → detail view
4. In the "LLM Evaluator (automated)" card, click **Request LLM Review**
5. Button should show "Évaluation en cours…" while waiting
6. Card should update in-place with a `Good` or `Bad` badge + critique text + **Re-run** button
7. Click **Re-run** — card should update again in-place
8. Refresh the page — rating and critique should persist (loaded from DB via `GET /api/contexts/<id>`)
