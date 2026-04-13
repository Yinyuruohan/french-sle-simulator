# Tools Directory

Python scripts that make API calls, process data, and execute specific tasks for the SLE exam simulator and LLM Grader.

## Tools

| Tool | Purpose | API Calls |
|---|---|---|
| `model_config.py` | `ModelConfig` dataclass + `load_default_configs()` — single source of truth for per-tool AI model settings | 0 |
| `generate_exam.py` | Generate SLE exam questions + explanations via AI API. Randomizes option positions post-generation. Supports single-context regeneration for quality fixes. | 1 (generation) + 0–N (regeneration) |
| `evaluate_exam.py` | Grade answers deterministically against the pre-generated answer key. Display pre-generated explanations from exam data. Log errors to tracking file. | 0 |
| `review_exam.py` | Unified conservative QA review of exam questions and explanations at temperature 0.1. Includes deterministic duplicate-option and structural-mismatch detection. Logs flagged issues to `system_error_tracking.md`. | 1 |
| `question_bank.py` | SQLite question bank: initialise DB, cache validated contexts, assemble instant exams, prefill bank, flag contexts, manage status transitions. | 0 |
| `grader_db.py` | Reviews table in the shared `question_bank.db`: initialise, CRUD, filtered queries, SHA-256 snapshot staleness detection. | 0 |

## Key Functions

### model_config.py
- `ModelConfig` — dataclass: `base_url`, `api_key`, `model`, `temperature`, `max_tokens`
- `load_default_configs()` — returns per-tool configs resolved from env vars (`GENERATE_*`, `EVALUATE_*`, `REVIEW_*`) with DeepSeek defaults

### generate_exam.py
- `generate_exam(num_questions, model_config)` — generate a full exam (2–20 questions) with questions and explanations in one API call
- `regenerate_context(context, contexts, start_qid, flagged_issues, model_config)` — replace a single flagged context using structured error details and structural validation
- `resave_exam_markdown(exam_data)` — re-save exam file after regeneration

### evaluate_exam.py
- `evaluate_exam(exam, user_answers)` — grade answers and return results with pre-generated explanations (no API call)
- `save_feedback_markdown(evaluation)` — write evaluation results to `.tmp/`
- `log_user_errors(session_id, evaluation)` — append incorrect items to `user_error_tracking.md`

### review_exam.py
- `review_exam_quality(exam_data, model_config)` — unified QA review: validates questions and explanations; runs deterministic checks first (duplicate options, structural mismatches), then AI-judgment checks at temperature 0.1
- `log_system_errors(session_id, review_result)` — append flagged issues to `system_error_tracking.md`

### question_bank.py
- `init_db()` — create the `contexts` table if it doesn't exist
- `save_contexts(contexts, session_id)` — insert or update contexts after generation
- `get_contexts_for_exam(num_questions, filters)` — assemble exam from bank using quality-aware ordering (`battle_tested` > `reviewed` > `warned`)
- `update_context_status(context_id, status)` — transition status (e.g., `reviewed` → `battle_tested`)
- `flag_context(context_id)` — increment `user_flags` to deprioritise in future exams
- `prefill_bank(target_count, model_config)` — generate and review contexts in bulk to pre-populate the bank

### grader_db.py
- `init_reviews_table()` — create the `reviews` table if it doesn't exist
- `cleanup_empty_reviews()` — delete rows where `expert_rating IS NULL` (startup cleanup)
- `get_contexts_for_review(filters)` — list contexts with optional filters (status, flagged, reviewed); LEFT JOIN with reviews
- `get_review(context_id)` — retrieve a single review row by context_id
- `save_review(context_id, expert_rating, expert_critique)` — create (with context snapshot) or update an existing review
- `get_context_data(context_id)` — read live context fields from the contexts table
- `is_snapshot_outdated(context_id)` — SHA-256 hash comparison of stored snapshot vs current context; returns `True`/`False`/`None`

## Conventions

- All tools load credentials from `.env` via `python-dotenv`
- AI API accessed via the `openai` SDK with a configurable `base_url` (default: DeepSeek `https://api.deepseek.com`)
- JSON response format enforced on all generation and review API calls
- Temperature by purpose: 0.7 (generation), 0.1 (review)
- `grader_db.py` never writes to the `contexts` table — read-only access only