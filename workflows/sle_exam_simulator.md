# SLE Written Expression Exam Simulator — Workflow SOP

## Objective

Generate realistic French SLE Written Expression practice exams, administer them through a web UI, grade answers, provide grammar feedback, and track errors for review. All content passes through an automated quality review agent before reaching the user.

## Required Inputs

- An API key for an OpenAI-compatible model endpoint, configured in `.env` (default: `DEEPSEEK_API_KEY`)
- Number of questions (5–40, chosen by the user at runtime)

## Tools Used

| Tool | Purpose |
|---|---|
| `tools/model_config.py` | `ModelConfig` dataclass + `load_default_configs()` — single source of truth for AI model settings |
| `tools/generate_exam.py` | Generates exam questions via AI API |
| `tools/review_exam.py` | Validates exam quality and feedback accuracy via AI API |
| `tools/evaluate_exam.py` | Grades answers, generates explanations, logs errors |

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
2. **Setup** — User selects number of questions (5–40); optionally expands "AI model settings" to override the model/endpoint/key for any tool independently
3. **Generation** — `generate_exam()` calls DeepSeek to produce questions:
   - ~50% fill-in-the-blank, ~50% error identification
   - Canadian federal workplace scenarios
   - Grammar coverage requirements ensure broad distribution across real SLE topics (no topic repeated more than twice)
   - Post-generation option shuffling (`_shuffle_options`) randomizes A/B/C/D positions for fill-in-blank questions so correct answers aren't predictably in one slot (error_identification questions are not shuffled — segment order must match passage labels)
   - Saves exam markdown to `.tmp/exam_YYYYMMDD_HHMMSS.md`
4. **Exam quality review** — `review_exam_quality()` validates the generated exam:
   - Deterministic pre-check: flags any question with duplicate option text
   - API review: checks passage grammar, answer key correctness, distractor validity
   - If critical issues found: `regenerate_context()` replaces affected contexts (max 1 retry per context)
     - Regeneration receives structured issue data (question_id, category, issue description) plus the original rejected context
     - Regenerated context must pass structural validation (correct IDs, all options present, no duplicates) or raises an error
     - Regeneration failures are surfaced to the user via warning banner, not silently swallowed
   - If warnings only: proceeds with flags stored in session state
   - All flagged issues (critical and warning) logged to `system_error_tracking.md`
   - Temperature: 0.1 (strict, consistent review)
5. **Exam** — Questions displayed with radio buttons. Strict examiner tone. Warning banner shown if any questions were flagged.
6. **Submission** — User submits answers
7. **Evaluation** — `evaluate_exam()` processes answers:
   - Deterministic scoring against answer key
   - DeepSeek API call for grammar explanations (wrong answers only)
   - Proportional level mapping: C (≥90%), B (≥70%), A (≥50%), Below A (<50%)
   - Saves feedback to `.tmp/feedback_YYYYMMDD_HHMMSS.md`
   - Appends errors to `user_error_tracking.md`
8. **Feedback quality review** — `review_feedback_quality()` validates explanations:
   - Checks grammar rule accuracy, reasoning correctness
   - If critical issues found: `regenerate_explanations()` re-generates only flagged explanations (max 1 retry)
     - Regeneration receives the previous rejected explanation and the reviewer's specific feedback (category + issue description)
     - Uses a corrective prompt that instructs the model to address the reviewer's concern and avoid repeating the same mistake
     - Regeneration failures are surfaced to the user via warning banner, not silently swallowed
   - Re-saves corrected feedback markdown after regeneration
   - All flagged issues logged to `system_error_tracking.md`
   - Results page shows severity-appropriate warnings: critical flags show a prominent warning, warning flags show a caption note
9. **Results** — Score, level, per-question breakdown with explanations

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

## Evaluation Prompt Design

The evaluation prompt:
- Receives only incorrect questions with user's wrong answer and correct answer
- Asks for structured response: why_incorrect, why_correct, grammar_rule
- Temperature: 0.3 (precise, consistent explanations)

## Quality Review Prompt Design

The review agent uses a **conservative role framing** — the reviewer is a "careful QA specialist" that only flags issues it is confident about, not a test designer. This avoids false positives while still catching real errors.

**Exam review checks:**
1. Is the passage grammatically correct French?
2. Is the marked correct answer the ONLY correct answer?
3. Are all distractors definitively wrong?
4. Are any two options identical or nearly identical? (also caught by deterministic pre-check)
5. For error_identification: is the planted error real?
6. Does question numbering match passage blank numbering?

**Feedback review checks:**
1. Is the cited grammar rule real and correctly stated?
2. Does the reasoning match the actual question content?
3. No hallucinated rules or exceptions?

**Severity levels:**
- **Critical** → requires regeneration (wrong answer key, multiple valid answers, duplicate options, misleading explanation)
- **Warning** → flagged but proceeds (marginally plausible distractor, imprecise label)

Temperature: 0.1 (deterministic, consistent judgments)
Regeneration cap: max 1 attempt per context/explanation (prevents loops and cost explosion)

**Regeneration prompt design:**
When critical issues are found, `regenerate_context()` receives structured error data (not raw text). The prompt includes:
- The original rejected passage and questions (so the model knows what to avoid)
- Each flagged issue with question_id, category, and description
- Explicit instructions: write a completely different passage, self-check each answer and distractor
- Post-regeneration structural validation ensures correct IDs, all options present, no duplicates

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

## Known Limitations

- Questions are AI-generated and pass through an automated quality review, but the reviewer uses the same AI model and may not catch all errors. Questions flagged with warnings should be reviewed critically.
- The scoring system is a simplified approximation, not the official PSC methodology.
- No timer is enforced (the real exam is 45 minutes for 40 questions).
- Error identification questions rely on the AI correctly placing errors in bolded segments.

## Future Improvements

- Add a countdown timer matching the official 45-minute window
- Implement a question bank to cache high-quality generated questions
- Add difficulty levels (A/B/C targeting)
- Export results to PDF
- Add a dashboard showing progress over time from the tracking file
