# French SLE Written Expression Simulator

An AI-powered practice tool for the Canadian federal Public Service Commission's **Second Language Evaluation (SLE) — Test of Written Expression**. Generates realistic exam questions, grades answers, and provides detailed French grammar feedback.

Built on the **WAT framework** (Workflows, Agents, Tools) using any OpenAI-compatible AI endpoint (default: DeepSeek) and Streamlit as the web UI.

## Features

- **Two question types** matching the official exam format:
  - Fill in the blank — workplace passages with numbered blanks, each with A/B/C/D choices
  - Error identification — passages with bolded segments, identify which contains errors
- **Canadian federal workplace contexts** — emails, memos, policies, meeting invitations
- **Bilingual interface** (English + French)
- **Configurable exam length** — 5 to 40 questions
- **Randomized answer positions** — correct answers are shuffled across A/B/C/D to prevent guessing patterns
- **Configurable AI model** — use any OpenAI-compatible endpoint (DeepSeek, OpenAI, Gemini, Ollama…) independently for generation, evaluation, and review — via `.env` or the in-app settings expander
- **Automated quality review** — conservative QA agent validates every exam before you see it:
  - Checks passage grammar, answer key correctness, distractor validity, duplicate options
  - Critical issues trigger automatic regeneration with structured error feedback
  - Deterministic duplicate-option detection runs before AI review
- **Detailed grammar feedback** — for each wrong answer: why incorrect, why correct, grammar rule
- **Feedback quality review** — grammar explanations are validated for accuracy before display
- **Simplified SLE level scoring** — C (>=90%), B (>=70%), A (>=50%), Below A (<50%)
- **Persistent error tracking** — logs user mistakes across sessions in `user_error_tracking.md`
- **System QA tracking** — logs all review-flagged issues to `system_error_tracking.md`

## Project Structure

```
french_sle_simulator/
├── app.py                           # Streamlit entry point (4 stages: welcome -> setup -> exam -> results)
├── tools/
│   ├── model_config.py              # ModelConfig dataclass + load_default_configs() — model settings
│   ├── generate_exam.py             # AI API: generate exam questions + option shuffling
│   ├── evaluate_exam.py             # AI API: grade + explain answers
│   └── review_exam.py               # AI API: conservative QA review of exams and feedback
├── tests/
│   ├── test_model_config.py         # Tests for model_config.py
│   └── test_generate_exam.py        # Tests for generate_exam.py ModelConfig wiring
├── workflows/
│   └── sle_exam_simulator.md        # SOP for the exam workflow
├── contexts/
│   └── fr-written-test-booklet-100919.pdf  # Official PSC test reference
├── .tmp/                            # Generated exams + feedback (disposable)
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

1. **Start an exam** — choose the number of questions (5-40); optionally configure model settings
2. **Generation** — AI generates questions; options are randomized; a conservative QA review validates quality and regenerates any flagged contexts
3. **Answer questions** — select A/B/C/D for each question across multiple contexts
4. **Evaluation** — answers are scored; grammar explanations generated for wrong answers; feedback is reviewed for accuracy
5. **Get results** — score, SLE level estimate, and per-question grammar explanations

## Exam Format

Questions are organized into **contexts** (numbered passages), each containing 1-2 questions:

- **Contexts** are numbered 1, 2, 3...
- **Questions** are numbered continuously across contexts: (1), (2), (3)...
- **Choices** use A, B, C, D (positions randomized per question)
- ~50% fill-in-the-blank, ~50% error identification

## Quality Assurance Pipeline

Every generated exam passes through a multi-layer quality check:

1. **Deterministic checks** — duplicate option detection (programmatic, no AI)
2. **AI review** — conservative QA agent at temperature 0.1 checks answer keys, distractors, passage grammar
3. **Targeted regeneration** — critical issues trigger context-level regeneration with structured error details and structural validation (max 1 retry per context)
4. **Feedback review** — grammar explanations are validated for rule accuracy and reasoning correctness
5. **Error logging** — all flagged issues are logged to `system_error_tracking.md` for monitoring

## Tech Stack

- **AI Engine:** Any OpenAI-compatible endpoint (default: DeepSeek `deepseek-chat`); configurable per tool
- **Web UI:** Streamlit
- **Framework:** WAT (Workflows, Agents, Tools)
- **Language:** Python 3.10+
- **Tests:** pytest (9 tests covering `ModelConfig` and tool wiring)

## Disclaimer

This is an **unofficial practice tool**. Results do not represent official PSC scores. The scoring thresholds are simplified proportional estimates, not the official PSC methodology. AI-generated questions pass through automated quality review but may occasionally contain errors — review critically.
