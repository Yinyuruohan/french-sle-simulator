# Agent Instructions

You're working on the **French SLE Written Expression Simulator** — an AI-powered practice tool for Canada's federal public service second language exam. The project uses the **WAT framework** (Workflows, Agents, Tools).

## Project Overview

This app generates realistic French SLE Written Expression exam questions via DeepSeek API, presents them through a Streamlit web UI, grades answers, provides grammar feedback, and tracks errors for adaptive learning.

**Key entry points:**
- `streamlit run app.py` — launches the web UI
- `tools/generate_exam.py` — generates exam questions (DeepSeek API)
- `tools/evaluate_exam.py` — grades answers and generates feedback (DeepSeek API)
- `tools/review_exam.py` — validates exam quality and feedback accuracy (DeepSeek API)
- `workflows/sle_exam_simulator.md` — full SOP for the exam workflow

## The WAT Architecture

**Layer 1: Workflows** — Markdown SOPs in `workflows/` defining objectives, inputs, tools, outputs, and edge cases.

**Layer 2: Agents** — Your role. Read workflows, run tools in sequence, handle failures, ask clarifying questions. Don't try to do everything directly — delegate execution to tools.

**Layer 3: Tools** — Python scripts in `tools/` that make API calls and process data. Credentials in `.env`. Deterministic, testable, fast.

## File Structure

```
app.py                    # Streamlit web UI (4 stages: welcome → setup → exam → results)
tools/
  generate_exam.py        # DeepSeek API call to generate contexts→questions with A/B/C/D
  evaluate_exam.py        # Grade answers, generate explanations, save feedback, track errors
  review_exam.py          # Adversarial QA review of exam questions and feedback explanations
workflows/
  sle_exam_simulator.md   # Full SOP for the exam workflow
contexts/
  fr-written-test-booklet-100919.pdf  # Official PSC test reference
.tmp/                     # Disposable: generated exam + feedback markdown files
user_error_tracking.md    # Persistent: cumulative error log across all sessions
system_error_tracking.md  # Persistent: review-flagged issues across sessions (system QA log)
.env                      # DEEPSEEK_API_KEY (never commit)
.env.template             # Template for .env
requirements.txt          # python-dotenv, requests, openai, streamlit
```

## Exam Data Structure

Exams use a **contexts → questions** structure:
- **Contexts** numbered 1, 2, 3... (each is a workplace passage)
- **Questions** numbered continuously across contexts: (1), (2), (3)...
- **Choices** use A, B, C, D (each question has its own set)
- Fill-in-blank contexts: 1–2 questions each
- Error identification contexts: exactly 1 question, option D = "Aucun des choix offerts."

## How to Operate

1. **Look for existing tools first** — check `tools/` before building anything new.
2. **Learn and adapt when things fail** — read error traces, fix scripts, update the workflow SOP.
3. **Keep workflows current** — update `workflows/sle_exam_simulator.md` when you discover constraints or better approaches. Don't create or overwrite workflows without asking.
4. **Check with me before running paid API calls** if you're debugging or experimenting.

## Key Technical Details

- **AI Engine:** DeepSeek via `openai` Python SDK with `base_url="https://api.deepseek.com"`, model `deepseek-chat`
- **Exam generation:** Single API call, JSON response format, temperature 0.7. Post-generation option shuffling randomizes A/B/C/D positions so the correct answer isn't predictable.
- **Evaluation:** Deterministic scoring + one API call for grammar explanations (temperature 0.3)
- **Quality review:** Adversarial QA agent (`tools/review_exam.py`) validates exam questions and feedback explanations at temperature 0.1. Includes deterministic duplicate-option detection. Critical issues trigger targeted regeneration with structured error details and structural validation (max 1 retry per context/explanation). Feedback regeneration includes the rejected explanation and reviewer's specific feedback so the model corrects the exact issue. Failures are surfaced to the user, not silently swallowed. All flagged issues logged to `system_error_tracking.md`.
- **Adaptive learning:** `generate_exam()` reads `user_error_tracking.md` to bias question generation toward weak grammar areas
- **Output files:** Exam and feedback markdown saved to `.tmp/`; user errors appended to `user_error_tracking.md`; system QA issues appended to `system_error_tracking.md`

## Bottom Line

You sit between what I want (workflows) and what gets done (tools). Read instructions, make smart decisions, call the right tools, recover from errors, and keep improving the system.
