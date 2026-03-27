# French SLE Written Expression Simulator

An AI-powered practice tool for the Canadian federal Public Service Commission's **Second Language Evaluation (SLE) — Test of Written Expression**. Generates realistic exam questions, grades answers, and provides detailed French grammar feedback.

Built on the **WAT framework** (Workflows, Agents, Tools) using any OpenAI-compatible AI endpoint (default: DeepSeek) and Streamlit as the web UI.

## Features

- **Two question types** matching the official exam format:
  - Fill in the blank — workplace passages with numbered blanks, each with A/B/C/D choices
  - Error identification — passages with bolded segments, identify which contains errors
- **Canadian federal workplace contexts** — emails, memos, policies, meeting invitations
- **Bilingual interface** (English + French)
- **Configurable exam length** — 2 to 20 questions
- **Randomized answer positions** — correct answers are shuffled across A/B/C/D to prevent guessing patterns
- **Configurable AI model** — use any OpenAI-compatible endpoint (DeepSeek, OpenAI, Gemini, Ollama...) independently for generation and review — via `.env` or the in-app settings expander
- **Question bank** — SQLite cache of validated contexts for instant exam assembly:
  - Quality-aware ordering: `battle_tested` > `reviewed` > `warned` > user-flagged
  - Pre-fill button to build up the bank ahead of time
  - Contexts upgrade to `battle_tested` after successful exam completion
- **Automated quality review** — conservative QA agent validates every exam before you see it:
  - Checks passage grammar, answer key correctness, distractor validity, explanation accuracy
  - Deterministic checks: duplicate options and structural mismatches (critical)
  - AI-judgment categories capped at warning severity
  - Critical issues trigger automatic regeneration (max 1 retry per context)
- **Inline grammar explanations** — every question includes `why_correct` and `grammar_rule`, generated alongside the questions (no extra API call)
- **User flagging** — flag individual contexts on the results screen; flagged contexts are deprioritized in future exams
- **Fully deterministic evaluation** — no API call needed; scores answers against the pre-generated answer key
- **Simplified SLE level scoring** — C (>=90%), B (>=70%), A (>=50%), Below A (<50%)
- **Persistent error tracking** — logs user mistakes across sessions in `user_error_tracking.md`
- **System QA tracking** — logs all review-flagged issues to `system_error_tracking.md`

## Project Structure

```
french_sle_simulator/
├── app.py                           # Streamlit entry point (4 stages: welcome -> setup -> exam -> results)
├── tools/
│   ├── model_config.py              # ModelConfig dataclass + load_default_configs() — model settings
│   ├── generate_exam.py             # AI API: generate exam questions + explanations + option shuffling
│   ├── evaluate_exam.py             # Deterministic grading using pre-generated explanations
│   ├── review_exam.py               # AI API: unified QA review of questions and explanations
│   └── question_bank.py             # SQLite question bank: cache, assemble, prefill, flag
├── tests/
│   ├── test_model_config.py         # Tests for model_config.py (6 tests)
│   ├── test_generate_exam.py        # Tests for generate_exam.py (6 tests)
│   ├── test_evaluate_exam.py        # Tests for evaluate_exam.py (4 tests)
│   ├── test_review_exam.py          # Tests for review_exam.py (5 tests)
│   └── test_question_bank.py        # Tests for question_bank.py (28 tests)
├── workflows/
│   └── sle_exam_simulator.md        # SOP for the exam workflow
├── contexts/
│   └── fr-written-test-booklet-100919.pdf  # Official PSC test reference
├── .tmp/                            # Generated exams + feedback (disposable)
├── question_bank.db                 # SQLite question bank cache (gitignored, auto-created)
├── user_error_tracking.md           # Persistent user error log (auto-created)
├── system_error_tracking.md         # Persistent system QA log (auto-created)
├── .env                             # API keys (gitignored)
├── .env.template                    # Environment variable template
├── requirements.txt                 # Python dependencies
├── CLAUDE.md                        # Agent operating instructions
└── README.md                        # This file
```

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure API key:**
   ```bash
   cp .env.template .env
   # Edit .env and set DEEPSEEK_API_KEY (or any OpenAI-compatible key — see .env.template)
   ```

3. **Run the app:**
   ```bash
   streamlit run app.py
   ```
   Open **http://localhost:8501** in your browser.

## How It Works

1. **Setup** — choose the number of questions (2-20); optionally configure model settings
2. **Start exam** — choose "Instant exam (from bank)" for cached questions or "Generate fresh (API)" for new ones
3. **Generation** (fresh only) — AI generates questions and explanations in one call; options are randomized; a unified QA review validates quality and regenerates any critical contexts
4. **Answer questions** — select A/B/C/D for each question across multiple contexts
5. **Results** — score, SLE level estimate, per-question grammar explanations; flag any questionable contexts

## API Call Summary

| Path | API Calls |
|---|---|
| Fresh exam | 2 (generate + review) |
| Cached exam (from bank) | 0 |

## Exam Format

Questions are organized into **contexts** (numbered passages), each containing 1-2 questions:

- **Contexts** are numbered 1, 2, 3...
- **Questions** are numbered continuously across contexts: (1), (2), (3)...
- **Choices** use A, B, C, D (positions randomized per question)
- ~50% fill-in-the-blank, ~50% error identification
- Grammar coverage: 11 real SLE topics, no topic repeated more than twice

## Quality Assurance Pipeline

Every generated exam passes through a multi-layer quality check:

1. **Deterministic checks** — duplicate option detection and structural mismatch validation (critical failures)
2. **Unified AI review** — conservative QA agent at temperature 0.1 checks answer keys, distractors, passage grammar, explanation accuracy, and grammar rules
3. **Targeted regeneration** — critical issues trigger context-level regeneration with structured error details (max 1 retry per context)
4. **Status tracking** — clean contexts cached as `reviewed`, contexts with warnings cached as `warned`
5. **Error logging** — all flagged issues are logged to `system_error_tracking.md` for monitoring

## Tech Stack

- **AI Engine:** Any OpenAI-compatible endpoint (default: DeepSeek `deepseek-chat`); configurable per tool
- **Web UI:** Streamlit
- **Database:** SQLite (question bank cache)
- **Framework:** WAT (Workflows, Agents, Tools)
- **Language:** Python 3.10+
- **Tests:** pytest (49 tests across 5 test modules)

## Disclaimer

This is an **unofficial practice tool**. Results do not represent official PSC scores. The scoring thresholds are simplified proportional estimates, not the official PSC methodology. AI-generated questions pass through automated quality review but may occasionally contain errors — review critically.
