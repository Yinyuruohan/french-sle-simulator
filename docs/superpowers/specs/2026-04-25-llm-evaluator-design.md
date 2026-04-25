# LLM Evaluator for Grader — Design Spec
**Date:** 2026-04-25

## Overview

Add an on-demand LLM evaluator to the LLM Grader detail view. The user clicks "Request LLM Review" in the existing "LLM Evaluator (automated)" card and receives an AI-generated rating ("Good" or "Bad") and critique for the context. The feature is available at any time, independent of expert review status.

---

## Architecture

Four layers are changed or added, following the existing WAT pattern:

```
UI (app.js)
  → POST /api/contexts/<id>/llm-review   (grader/app.py)
    → evaluate_context()                  (tools/llm_evaluator.py)  ← new
    → save_llm_review()                   (tools/grader_db.py)       ← new function
```

---

## Layer 1 — `tools/llm_evaluator.py` (new file)

Single public function:

```python
def evaluate_context(context_data: dict, model_config: ModelConfig) -> dict:
    # Returns {"rating": "Good"|"Bad", "critique": "<2-4 sentences>"}
```

- Reads judge criteria from `LLM_judge_prompt.md` (project root)
- Serializes context: passage, questions, options, correct answers, explanations
- Calls LLM via OpenAI SDK at temperature 0.1
- Parses response to extract rating and critique
- Model config uses `EVALUATOR_*` env vars (`EVALUATOR_API_KEY`, `EVALUATOR_BASE_URL`, `EVALUATOR_MODEL`), falling back to DeepSeek defaults

---

## Layer 2 — `tools/grader_db.py` (new function)

```python
def save_llm_review(context_id: str, llm_rating: str, llm_critique: str) -> dict | None:
    # Returns {"updated_at": "<iso>"} or None if context not found
```

Two cases:
- **Row exists**: UPDATE `llm_evaluator_rating`, `llm_evaluator_critique`, `updated_at` only; all other fields untouched
- **No row yet**: INSERT new row with context snapshot, `llm_evaluator_rating`, `llm_evaluator_critique`; `expert_rating` and `agreement` left NULL

`save_review()` is unchanged.

---

## Layer 3 — `grader/app.py` (new endpoint)

```
POST /api/contexts/<context_id>/llm-review
```

1. `get_context_data(context_id)` → 404 if not found
2. `evaluate_context(context_data, evaluator_model_config)`
3. `save_llm_review(context_id, rating, critique)`
4. Returns `{"rating": ..., "critique": ..., "updated_at": ...}`

Evaluator model config loaded at startup from `EVALUATOR_*` env vars, passed into `create_app()`. No changes to existing routes.

---

## Layer 4 — `grader/static/app.js` + `style.css` (UI)

The "LLM Evaluator (automated)" card has three states:

| State | UI |
|---|---|
| Not yet evaluated | "Request LLM Review" button |
| Loading | Button disabled, loading text |
| Done | Rating badge + critique text + "Re-run" button |

On button click:
1. Disable button, show loading state
2. `POST /api/contexts/<context_id>/llm-review`
3. On success: update card in-place (no page reload)
4. On error: show toast, re-enable button

Reuses existing CSS classes: `.badge-good`, `.badge-bad`, `.btn-primary`. No new classes needed.

---

## Data Flow

```
question_bank.db
  contexts table  → read-only by evaluator (get_context_data)
  reviews table   → written by save_llm_review
                    columns: llm_evaluator_rating, llm_evaluator_critique, updated_at
```

`agreement` column is left for a future phase.

---

## Environment Variables

| Variable | Purpose | Fallback |
|---|---|---|
| `EVALUATOR_API_KEY` | LLM evaluator API key | `DEEPSEEK_API_KEY` |
| `EVALUATOR_BASE_URL` | LLM evaluator base URL | `https://api.deepseek.com` |
| `EVALUATOR_MODEL` | LLM evaluator model name | `deepseek-v4-pro` |

---

## Files Changed

| File | Change |
|---|---|
| `tools/llm_evaluator.py` | New — LLM call + response parsing |
| `tools/grader_db.py` | Add `save_llm_review()` |
| `grader/app.py` | Add `POST /api/contexts/<id>/llm-review`, load evaluator config |
| `grader/static/app.js` | Replace static llmSection with interactive states |
| `.env.template` | Add `EVALUATOR_*` vars |
