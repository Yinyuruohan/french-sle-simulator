# Agent Instructions

You're working on the **French SLE Written Expression Simulator** — an AI-powered practice tool for Canada's federal public service second language exam. The project uses the **WAT framework** (Workflows, Agents, Tools).

## Project Overview

This app generates realistic French SLE Written Expression exam questions via a configurable AI API (default: DeepSeek), presents them through a Streamlit web UI, grades answers, provides grammar feedback, and tracks errors for review.

**Key entry points:**
- `streamlit run app.py` — launches the web UI (port 8501)
- `python grader/app.py` — launches the LLM Grader expert review interface (port 5001)
- `python flashcard/app.py` — launches the Flashcard Study app (port 5002)
- `tools/model_config.py` — `ModelConfig` dataclass + `load_default_configs()`; single source of truth for AI model settings
- `tools/generate_exam.py` — generates exam questions (AI API)
- `tools/evaluate_exam.py` — grades answers and displays pre-generated feedback (no AI API)
- `tools/review_exam.py` — validates exam quality and feedback accuracy (AI API)
- `tools/question_bank.py` — SQLite question bank: cache validated contexts, assemble instant exams
- `tools/flashcard_db.py` — shared inbox helper; lets `app.py` write vocab words to `flashcard/flashcard.db` without requiring the flashcard server to be running
- `workflows/sle_exam_simulator.md` — full SOP for the exam workflow

## The WAT Architecture

**Layer 1: Workflows** — Markdown SOPs in `workflows/` defining objectives, inputs, tools, outputs, and edge cases.

**Layer 2: Agents** — Your role. Read workflows, run tools in sequence, handle failures, ask clarifying questions. Don't try to do everything directly — delegate execution to tools.

**Layer 3: Tools** — Python scripts in `tools/` that make API calls and process data. Credentials in `.env`. Deterministic, testable, fast.

## File Structure

```
app.py                    # Streamlit web UI (4 stages: welcome → setup → exam → results)
grader/
  app.py                  # Flask app: REST API + static file serving for expert review
  batch.py                # Batch Excel export/import: export_to_excel(), import_from_excel()
  static/
    index.html            # SPA entry point (list + detail views, hash-based routing)
    style.css             # Grader styles (Plus Jakarta Sans, blue palette)
    app.js                # Vanilla JS: API calls, view rendering, state management
flashcard/
  app.py                  # Flask server: REST API + Vite SPA serving (port 5002)
  flashcard_api.py        # API routes: decks, cards, inbox, study sessions
  flashcard_db.py         # SQLite schema init + deck/card/inbox/session CRUD
  context/
    lexique-backup-*.json # Seed vocabulary JSON (loaded on first run)
  src/                    # React 18 + Vite 5 SPA source
    main.jsx              # App entry + HashRouter + layout
    views/
      Decks.jsx           # Deck list + create/delete
      Cards.jsx           # Card list + add/edit/delete
      Inbox.jsx           # Vocab inbox: AI generate → review → commit to deck
      StudySession.jsx    # Study modes: flip, MCQ, type-in; session tracking
      Progress.jsx        # Mastery bars + session history
  static/dist/            # Vite build output (committed; served by Flask)
  flashcard.db            # SQLite database (gitignored, auto-created)
tools/
  model_config.py         # ModelConfig dataclass + load_default_configs(); per-tool AI model settings
  generate_exam.py        # AI API call to generate contexts→questions with A/B/C/D
  evaluate_exam.py        # Grade answers deterministically, display pre-generated feedback (no AI API)
  review_exam.py          # Conservative QA review of exam questions and feedback explanations
  question_bank.py        # SQLite question bank: cache, assemble, prefill
  grader_db.py            # Reviews table: init, CRUD, filtered queries, staleness detection
  flashcard_db.py         # Shared inbox helper: add_to_inbox(); writes to flashcard/flashcard.db
  llm_evaluator.py        # LLM judge: evaluate_context() rates a context Good/Bad with critique
LLM_judge_prompt.md       # System prompt for the LLM evaluator judge (SLE criteria + output format)
tests/
  test_model_config.py    # Unit tests for model_config.py (6 tests)
  test_generate_exam.py   # ModelConfig wiring tests for generate_exam.py (3 tests)
  test_question_bank.py   # Unit tests for question_bank.py (17 tests)
  test_grader_db.py       # Unit tests for grader_db.py (24 tests)
  test_grader_api.py      # Integration tests for grader Flask API (17 tests)
  test_grader_batch.py    # Unit + integration tests for batch export/import (28 tests)
  test_llm_evaluator.py   # Unit tests for llm_evaluator.py (4 tests)
workflows/
  sle_exam_simulator.md   # Full SOP for the exam workflow
contexts/
  fr-written-test-booklet-100919.pdf  # Official PSC test reference
.tmp/                     # Disposable: generated exam + feedback markdown files
user_error_tracking.md    # Persistent: cumulative error log across all sessions
system_error_tracking.md  # Persistent: review-flagged issues across sessions (system QA log)
question_bank.db          # Persistent: SQLite question bank cache (gitignored, can be deleted and rebuilt)
.env                      # API keys (never commit); DEEPSEEK_API_KEY + optional per-tool overrides
.env.template             # Template for .env
requirements.txt          # python-dotenv, requests, openai, streamlit, flask, openpyxl
```

## Exam Data Structure

Exams use a **contexts → questions** structure:
- **Contexts** numbered 1, 2, 3... (each is a workplace passage)
- **Questions** numbered continuously across contexts: (1), (2), (3)...
- **Choices** use A, B, C, D (each question has its own set)
- Fill-in-blank contexts: 1–2 questions each
- Error identification contexts: exactly 1 question; passage segments labeled **(A)**, **(B)**, **(C)**; options A/B/C contain segment text only; option D = "Aucun des choix offerts." (fixed, never shuffled)

## How to Operate

1. **Look for existing tools first** — check `tools/` before building anything new.
2. **Learn and adapt when things fail** — read error traces, fix scripts, update the workflow SOP.
3. **Keep workflows current** — update `workflows/sle_exam_simulator.md` when you discover constraints or better approaches. Don't create or overwrite workflows without asking.
4. **Check with me before running paid API calls** if you're debugging or experimenting.

## Key Technical Details

- **AI Engine:** Any OpenAI-compatible endpoint via `openai` Python SDK. Default: DeepSeek (`base_url="https://api.deepseek.com"`, model `deepseek-v4-pro`). Per-tool overrides via `GENERATE_*`, `EVALUATE_*`, `REVIEW_*`, `EVALUATOR_*` env vars or the in-app "AI model settings" expander. `tools/model_config.py` is the single source of truth.
- **Flashcard app:** `flashcard/app.py` — Flask 3 server on port 5002 serving a React 18 + Vite 5 SPA (HashRouter). `flashcard/flashcard_db.py` owns all SQLite schema and CRUD for decks, cards, inbox, and study sessions. `tools/flashcard_db.py` is a lightweight shared helper (just `add_to_inbox()`) that lets `app.py` write vocab words to `flashcard/flashcard.db` without importing Flask. The Vite build output (`flashcard/static/dist/`) is committed so the server works with no Node.js tooling in production.
- **LLM Evaluator:** `tools/llm_evaluator.py` — `evaluate_context(context_data, model_config)` calls the LLM judge (`LLM_judge_prompt.md` as system prompt) and returns `{"rating": "Good"|"Bad", "critique": "..."}`. Configured via `EVALUATOR_*` env vars (falls back to `DEEPSEEK_API_KEY` + `deepseek-v4-pro`). Uses `max_tokens=4096` to accommodate reasoning model chain-of-thought overhead.
- **Exam generation:** Single API call produces questions AND explanations (why_correct + grammar_rule), JSON response format, temperature 0.7, max_tokens 16000. ~50% fill-in-blank, ~50% error identification, 2-20 questions. Prompt enforces broad grammar coverage: 11 real SLE topics, no topic repeated more than twice. Explanations must not reference option letters (shuffled post-generation). Post-generation option shuffling randomizes A/B/C/D for fill-in-blank questions; error identification options are never shuffled.
- **Evaluation:** Fully deterministic — no API call. Scores answers against the answer key and displays pre-generated explanations from exam data.
- **Quality review:** Single unified review (`review_exam_quality()`) validates questions AND explanations at temperature 0.1. Deterministic pre-checks: duplicate options and structural mismatches (passage blanks vs question IDs, error-ID segments vs options). Only deterministic failures (`duplicate_options`, `structural_mismatch`) are critical; all 11 AI-judgment categories are capped at "warning". Contexts with warnings cache as `warned` (never upgrade to `battle_tested`). User flagging deprioritizes contexts in assembly. Critical issues trigger targeted regeneration (max 1 retry per context). All flagged issues logged to `system_error_tracking.md`.
- **Pipeline:** 2 API calls per fresh exam (generate + review), 0 for cached exams. Previously was 4 calls.
- **Output files:** Exam and feedback markdown saved to `.tmp/`; user errors appended to `user_error_tracking.md`; system QA issues appended to `system_error_tracking.md`

## Bottom Line

You sit between what I want (workflows) and what gets done (tools). Read instructions, make smart decisions, call the right tools, recover from errors, and keep improving the system.
