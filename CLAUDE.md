# Agent Instructions

You're working on the **French SLE Written Expression Simulator** — an AI-powered practice tool for Canada's federal public service second language exam. The project uses the **WAT framework** (Workflows, Agents, Tools).

## Project Overview

This app generates realistic French SLE Written Expression exam questions via a configurable AI API (default: DeepSeek), presents them through a Streamlit web UI, grades answers, provides grammar feedback, and tracks errors for review.

**Key entry points:**
- `streamlit run app.py` — launches the web UI
- `tools/model_config.py` — `ModelConfig` dataclass + `load_default_configs()`; single source of truth for AI model settings
- `tools/generate_exam.py` — generates exam questions (AI API)
- `tools/evaluate_exam.py` — grades answers and generates feedback (AI API)
- `tools/review_exam.py` — validates exam quality and feedback accuracy (AI API)
- `workflows/sle_exam_simulator.md` — full SOP for the exam workflow

## The WAT Architecture

**Layer 1: Workflows** — Markdown SOPs in `workflows/` defining objectives, inputs, tools, outputs, and edge cases.

**Layer 2: Agents** — Your role. Read workflows, run tools in sequence, handle failures, ask clarifying questions. Don't try to do everything directly — delegate execution to tools.

**Layer 3: Tools** — Python scripts in `tools/` that make API calls and process data. Credentials in `.env`. Deterministic, testable, fast.

## File Structure

```
app.py                    # Streamlit web UI (4 stages: welcome → setup → exam → results)
tools/
  model_config.py         # ModelConfig dataclass + load_default_configs(); per-tool AI model settings
  generate_exam.py        # AI API call to generate contexts→questions with A/B/C/D
  evaluate_exam.py        # Grade answers, generate explanations, save feedback, track errors
  review_exam.py          # Conservative QA review of exam questions and feedback explanations
tests/
  test_model_config.py    # Unit tests for model_config.py (6 tests)
  test_generate_exam.py   # ModelConfig wiring tests for generate_exam.py (3 tests)
workflows/
  sle_exam_simulator.md   # Full SOP for the exam workflow
contexts/
  fr-written-test-booklet-100919.pdf  # Official PSC test reference
.tmp/                     # Disposable: generated exam + feedback markdown files
user_error_tracking.md    # Persistent: cumulative error log across all sessions
system_error_tracking.md  # Persistent: review-flagged issues across sessions (system QA log)
.env                      # API keys (never commit); DEEPSEEK_API_KEY + optional per-tool overrides
.env.template             # Template for .env
requirements.txt          # python-dotenv, requests, openai, streamlit
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

- **AI Engine:** Any OpenAI-compatible endpoint via `openai` Python SDK. Default: DeepSeek (`base_url="https://api.deepseek.com"`, model `deepseek-chat`). Per-tool overrides via `GENERATE_*`, `EVALUATE_*`, `REVIEW_*` env vars or the in-app "AI model settings" expander. `tools/model_config.py` is the single source of truth.
- **Exam generation:** Single API call, JSON response format, temperature 0.7. ~50% fill-in-blank, ~50% error identification. Prompt enforces broad grammar coverage: 11 real SLE topics, no topic repeated more than twice. Post-generation option shuffling randomizes A/B/C/D for fill-in-blank questions; error identification options are never shuffled (segment order must match passage labels).
- **Evaluation:** Deterministic scoring + one API call for grammar explanations (temperature 0.3)
- **Quality review:** Conservative QA agent (`tools/review_exam.py`) validates exam questions and feedback explanations at temperature 0.1. Includes deterministic duplicate-option detection. `_enforce_severity_rules()` caps `weak_distractor`, `topic_mismatch`, and `misleading_explanation` flags at "warning" regardless of AI output. Critical issues trigger targeted regeneration (max 1 retry per context/explanation). Failures are surfaced to the user, not silently swallowed. All flagged issues logged to `system_error_tracking.md`.
- **Output files:** Exam and feedback markdown saved to `.tmp/`; user errors appended to `user_error_tracking.md`; system QA issues appended to `system_error_tracking.md`

## Bottom Line

You sit between what I want (workflows) and what gets done (tools). Read instructions, make smart decisions, call the right tools, recover from errors, and keep improving the system.
