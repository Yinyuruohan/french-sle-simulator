# SLE Written Expression Exam Simulator — Workflow SOP

## Objective

Generate realistic French SLE Written Expression practice exams, administer them through a web UI, grade answers, provide grammar feedback, and track errors for review. All content passes through an automated quality review agent before reaching the user.

## Required Inputs

- An API key for an OpenAI-compatible model endpoint, configured in `.env` (default: `DEEPSEEK_API_KEY`)
- Number of questions (2–20, chosen by the user at runtime)

## Tools Used

| Tool | Purpose |
|---|---|
| `tools/model_config.py` | `ModelConfig` dataclass + `load_default_configs()` — single source of truth for AI model settings |
| `tools/generate_exam.py` | Generates exam questions via AI API |
| `tools/review_exam.py` | Unified quality review of exam questions and explanations via AI API |
| `tools/evaluate_exam.py` | Deterministic grading using pre-generated explanations, logs errors |
| `tools/question_bank.py` | Caches validated contexts in SQLite; assembles instant exams from cache; user flagging |

## How to Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open the URL shown in the terminal (typically `http://localhost:8501`).

**Model configuration** (`.env`):
- `DEEPSEEK_API_KEY` — used by all three tools as the default key (with `base_url=https://api.deepseek.com`, model `deepseek-chat`)
- Optional per-tool overrides: `GENERATE_API_KEY/BASE_URL/MODEL`, `EVALUATE_API_KEY/BASE_URL/MODEL`, `REVIEW_API_KEY/BASE_URL/MODEL`
- Any OpenAI-compatible endpoint is supported (e.g. Gemini, OpenAI, local Ollama)
- Per-session overrides are also available via the "AI model settings (optional)" expander on the setup screen

## Workflow Steps

1. **Welcome screen** — User clicks "Start a writing exam"
2. **Setup** — User selects number of questions (2–20); optionally expands "AI model settings" to override the model/endpoint/key for any tool independently. Displays question bank stats (including warned count) and a "Pre-fill bank" button.
3. **Cache check** — `assemble_exam_from_cache()` checks the question bank:
   - Sufficient cache → assembles exam instantly, skips generation and review
   - Partial cache → user chooses: shorter instant exam or generate fresh
   - Empty cache → proceeds to fresh generation
4. **Generation** — `generate_exam()` calls the AI API to produce questions AND explanations in a single call:
   - ~50% fill-in-the-blank, ~50% error identification
   - Canadian federal workplace scenarios
   - Grammar coverage requirements ensure broad distribution across real SLE topics (no topic repeated more than twice)
   - Each question includes `explanation` with `why_correct` and `grammar_rule` (no option letter references — options are shuffled post-generation)
   - Post-generation option shuffling (`_shuffle_options`) randomizes A/B/C/D positions for fill-in-blank questions so correct answers aren't predictably in one slot (error_identification questions are not shuffled — segment order must match passage labels)
   - Saves exam markdown to `.tmp/exam_YYYYMMDD_HHMMSS.md`
5. **Unified quality review** — `review_exam_quality()` validates questions AND explanations in a single call:
   - Deterministic pre-checks: flags duplicate option text and structural mismatches (passage blank numbering vs question IDs, error-ID segment labels vs options)
   - API review: checks passage grammar, answer key correctness, distractor validity, explanation accuracy, grammar rule correctness
   - **Only deterministic failures are critical** (`duplicate_options`, `structural_mismatch`). All AI-judgment categories are capped at "warning" severity.
   - If critical issues found: `regenerate_context()` replaces affected contexts (max 1 retry per context)
     - Regeneration receives structured issue data and the original rejected context
     - Regenerated context includes explanations and must pass structural validation
     - Regeneration failures are surfaced to the user via warning banner
   - Contexts with warnings are cached as `warned`; clean contexts are cached as `reviewed`
   - All flagged issues (critical and warning) logged to `system_error_tracking.md`
   - Temperature: 0.1 (strict, consistent review)
6. **Exam** — Questions displayed with radio buttons. Warning banner shown if exam contains `warned` contexts. Per-context "Flag quality issue" expander lets users report problems.
7. **Submission** — User submits answers
8. **Evaluation** — Fully deterministic, no API call needed:
   - Deterministic scoring against answer key
   - Pre-generated explanations displayed from exam data (why_correct + grammar_rule)
   - Proportional level mapping: C (≥90%), B (≥70%), A (≥50%), Below A (<50%)
   - Saves feedback to `.tmp/feedback_YYYYMMDD_HHMMSS.md`
   - Appends errors to `user_error_tracking.md`
   - Post-evaluation: `upgrade_to_battle_tested()` promotes `reviewed` contexts (warned contexts stay permanently warned)
9. **Results** — Score, level, per-question breakdown with explanations. Warned contexts show a caption. Explanation-related flags from the unified review are surfaced with severity-appropriate warnings.

## Exam Generation Prompt Design

The generation prompt includes:
- System role: expert PSC French test designer
- Format rules: two question types, 4 options, workplace contexts
- Few-shot examples from the official PSC test booklet (hardcoded)
- Requested question count and type mix
- Grammar coverage requirements: explicit topic distribution rules ensuring variety across real SLE topics
- JSON output format specification

Temperature: 0.7 (balanced creativity for varied questions)

Post-processing: `_shuffle_options()` randomizes the A/B/C/D positions for fill-in-blank questions so the correct answer is uniformly distributed. Error_identification questions are skipped entirely — their options must stay in the same order as the labeled passage segments (A), (B), (C), with D always being "Aucun des choix offerts."

## Evaluation (Deterministic)

Evaluation is fully deterministic — no API call needed. Scoring compares user answers to the pre-generated answer key. Pre-generated explanations (why_correct + grammar_rule) are displayed directly from the exam data.

## Unified Quality Review Prompt Design

The review agent uses a **conservative role framing** — the reviewer is a "careful QA specialist" that only flags issues it is confident about, not a test designer. A single unified review validates questions, answer keys, distractors, passage grammar, AND explanations.

**Unified review checks:**
1. Is the passage grammatically correct French?
2. Is the marked correct answer the ONLY correct answer?
3. Are all distractors definitively wrong?
4. Are any two options identical or nearly identical? (also caught by deterministic pre-check)
5. For error_identification: is the planted error real?
6. Does question numbering match passage blank numbering? (deterministic structural check)
7. Is the cited grammar rule real and correctly stated?
8. Does the reasoning match the actual question content?
9. No hallucinated rules or exceptions?

**Severity levels:**
- **Critical** → requires regeneration. Only deterministic failures: `duplicate_options`, `structural_mismatch`
- **Warning** → flagged but proceeds. All AI-judgment categories: `wrong_answer_key`, `multiple_correct`, `no_real_error`, `passage_grammar_error`, `weak_distractor`, `topic_mismatch`, `incorrect_rule`, `wrong_reasoning`, `misleading_explanation`, `hallucinated_rule`, `inconsistent_with_question`

Temperature: 0.1 (deterministic, consistent judgments)
Regeneration cap: max 1 attempt per context (prevents loops and cost explosion)

**Context status after review:**
- No warnings → `reviewed`
- Has warnings → `warned` (stays permanently, never upgrades to `battle_tested`)
- After successful exam usage: `reviewed` → `battle_tested`

**User flagging:**
Users can flag individual contexts during exams via a per-context dropdown (categories: Wrong answer key, Multiple correct answers, Unclear passage, Bad explanation, Other). Flagged contexts get `user_flags` incremented and are deprioritized in future assembly.

**Assembly priority:** unflagged `battle_tested` > unflagged `reviewed` > unflagged `warned` > user-flagged contexts.

**Regeneration prompt design:**
When critical issues are found, `regenerate_context()` receives structured error data (not raw text). The prompt includes:
- The original rejected passage and questions (so the model knows what to avoid)
- Each flagged issue with question_id, category, and description
- Explicit instructions: write a completely different passage, self-check each answer and distractor
- Explanation requirement: regenerated contexts include explanations (no option letter references)
- Post-regeneration structural validation ensures correct IDs, all options present, no duplicates

## API Call Summary

| Step | Calls |
|---|---|
| Generate (questions + explanations) | 1 |
| Unified review (questions + explanations) | 1 |
| Evaluation (deterministic) | 0 |
| **Total (fresh exam)** | **2** |
| **Total (cached exam)** | **0** |

## Scoring Thresholds

| Level | Threshold | Rationale |
|---|---|---|
| C | ≥ 90% | Advanced proficiency |
| B | ≥ 70% | Intermediate proficiency |
| A | ≥ 50% | Basic proficiency |
| Below A | < 50% | Insufficient |

These are simplified proportional thresholds scaled to the user's chosen number of questions. They are **not** the official PSC scoring brackets.

## Output Files

| File | Location | Persistence |
|---|---|---|
| Exam markdown | `.tmp/exam_*.md` | Disposable |
| Feedback markdown | `.tmp/feedback_*.md` | Disposable |
| User error tracking | `user_error_tracking.md` | Persistent (append-only, user mistakes) |
| System error tracking | `system_error_tracking.md` | Persistent (append-only, review-flagged QA issues) |
| Question bank | `question_bank.db` | Persistent (SQLite cache, can be deleted and rebuilt) |

## Known Limitations

- Questions are AI-generated and pass through an automated quality review, but the reviewer uses the same AI model and may not catch all errors. Questions flagged with warnings should be reviewed critically.
- The scoring system is a simplified approximation, not the official PSC methodology.
- No timer is enforced (the real exam is 45 minutes for 40 questions).
- Error identification questions rely on the AI correctly placing errors in bolded segments.

## Future Improvements

- Add a countdown timer matching the official 45-minute window
- Add difficulty levels (A/B/C targeting)
- Export results to PDF
- Add a dashboard showing progress over time from the tracking file
