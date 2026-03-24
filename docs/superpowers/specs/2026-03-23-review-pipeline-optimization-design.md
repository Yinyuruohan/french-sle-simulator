# Review Pipeline Optimization — Design Spec

## Problem

The current exam lifecycle uses up to 4 API calls (generate, review questions, evaluate+explain, review explanations). The generation review has a high false-positive rate — AI-judgment categories like `multiple_correct`, `wrong_answer_key`, and `no_real_error` frequently block caching of valid questions. This makes pre-fill unreliable and the overall pipeline slow and expensive.

## Goals

1. **Reduce API calls** from 4 to 2 per exam lifecycle
2. **Increase cache fill rate** by limiting critical severity to deterministic/structural failures only
3. **Preserve quality signals** via a `warned` status, user flagging, and battle-testing
4. **Maintain transparency** so users see quality warnings in the UI

## Decisions

### D1: Merge generation and explanation into one API call
The generation prompt produces contexts, questions, correct answers, AND explanations (`why_correct` + `grammar_rule`) in a single call. This eliminates the separate `_generate_explanations()` call during evaluation.

### D2: Merge both review steps into one unified review call
A single review call validates questions, answer keys, distractors, passage grammar, AND explanations. This eliminates the separate `review_feedback_quality()` call.

### D3: Evaluation becomes fully deterministic
Scoring compares user answers to the pre-generated answer key. Pre-generated explanations are displayed directly. No API call needed.

### D4: Only deterministic failures are critical
- **Critical:** `duplicate_options` (detected by deterministic `_check_duplicate_options()`), `structural_mismatch` (detected by new deterministic `_check_structural_mismatch()` — validates question_id numbering matches passage blank numbering, and error-ID segment labels match options)
- **Warning:** All AI-judgment categories — `wrong_answer_key`, `multiple_correct`, `no_real_error`, `passage_grammar_error`, `weak_distractor`, `topic_mismatch`, `incorrect_rule`, `wrong_reasoning`, `misleading_explanation`, `hallucinated_rule`, `inconsistent_with_question`

### D5: New `warned` status for soft quarantine
Contexts with warning flags cache as `warned` instead of `reviewed`. Both upgrade to `battle_tested` after a successful exam cycle.

### D6: Assembly prefers higher-quality contexts
Order: unflagged `battle_tested` > unflagged `reviewed` > unflagged `warned` > user-flagged contexts.

### D7: Users can flag quality issues during exams
A per-context flag button lets users report problems. A single flag (`user_flags >= 1`) deprioritizes the context in future assembly.

## Architecture

### New Exam Lifecycle

```
Pre-fill path:
  generate_exam() [1 API call] → unified review [1 API call] → cache (reviewed/warned)

Fresh exam path:
  generate_exam() [1 API call] → unified review [1 API call] → user takes exam → deterministic scoring [0 API calls]

Cached exam (reviewed/warned):
  assemble from cache [0 API calls] → user takes exam → deterministic scoring [0 API calls]

Cached exam (battle_tested):
  assemble from cache [0 API calls] → user takes exam → deterministic scoring [0 API calls]
```

### API Call Comparison

| Step | Before | After |
|---|---|---|
| Generate | Questions only (1 call) | Questions + explanations (1 call) |
| Review questions | Separate call (1 call) | Merged unified review (1 call) |
| Evaluate + explain | Score + explanations (1 call) | Deterministic scoring (0 calls) |
| Review explanations | Separate call (1 call) | Covered in unified review (0 calls) |
| **Total** | **4 calls** | **2 calls** |

## Data Model

### `contexts` table changes

No schema migration needed — `status` is already TEXT, `user_flags` is a new column.

```sql
-- Existing columns (no change):
context_id TEXT PRIMARY KEY,
type TEXT NOT NULL,
passage TEXT NOT NULL,
questions_json TEXT NOT NULL,      -- now includes explanation per question
num_questions INTEGER NOT NULL,
grammar_topics TEXT NOT NULL,
status TEXT NOT NULL DEFAULT 'reviewed',  -- values: 'reviewed', 'warned', 'battle_tested'
source_session TEXT NOT NULL,
created_at TEXT NOT NULL,
times_served INTEGER NOT NULL DEFAULT 0,
passage_hash TEXT NOT NULL,
last_incorrect INTEGER NOT NULL DEFAULT 0

-- New column:
user_flags INTEGER NOT NULL DEFAULT 0
```

### Question JSON structure change

Before (explanations added later during evaluation):
```json
{
  "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
  "correct_answer": "B",
  "grammar_topic": "agreement",
  "explanation": null
}
```

After (explanations generated upfront):
```json
{
  "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
  "correct_answer": "B",
  "grammar_topic": "agreement",
  "explanation": {
    "why_correct": "...",
    "grammar_rule": "..."
  }
}
```

### Context status lifecycle

```
Generation + Review:
  No warnings  → status = 'reviewed'
  Has warnings → status = 'warned'

After exam usage (battle-testing):
  reviewed → battle_tested
  warned   → battle_tested
```

## Module Interface Changes

### `tools/generate_exam.py`

**`generate_exam()`** — Prompt change only. The generation prompt expands to produce `explanation` with `why_correct` and `grammar_rule` for each question. Output JSON structure includes explanations. `_shuffle_options()` already updates `correct_answer` to the new letter after shuffling; explanations don't reference option letters, so shuffling is safe. `max_tokens` should increase from 12000 to 20000 to accommodate the additional explanation text; the existing retry-on-truncation logic handles edge cases.

### `tools/review_exam.py`

**`review_exam_quality()`** — Unified review. The system prompt and user prompt expand to also validate explanations (rule accuracy, reasoning correctness, hallucinations, consistency). Returns a single `flagged_questions` list covering both question and explanation issues. The `_build_exam_review_prompt()` serialization must include each question's explanation data so the reviewer can validate it.

**New deterministic check: `_check_structural_mismatch()`** — Validates question_id numbering matches passage blank markers for fill-in-blank questions, and error-ID segment labels (A)/(B)/(C) match options A/B/C. Runs alongside `_check_duplicate_options()` before the API call.

**Eliminated:**
- `review_feedback_quality()`
- `_build_feedback_review_prompt()`
- `FEEDBACK_REVIEW_SYSTEM` prompt
- `FEEDBACK_WARNING_ONLY_CATEGORIES` (merged into `EXAM_WARNING_ONLY_CATEGORIES`)

**Severity enforcement change:**
```python
# Before:
EXAM_WARNING_ONLY_CATEGORIES = {"weak_distractor", "topic_mismatch"}

# After:
EXAM_WARNING_ONLY_CATEGORIES = {
    "weak_distractor", "topic_mismatch",
    "wrong_answer_key", "multiple_correct",
    "no_real_error", "passage_grammar_error",
    "incorrect_rule", "wrong_reasoning",
    "misleading_explanation", "hallucinated_rule",
    "inconsistent_with_question",
}
```

### `tools/evaluate_exam.py`

**`evaluate_exam()`** — Fully deterministic. Compares user answers to `correct_answer`, pulls pre-generated explanations from exam data. No API call, no `model_config` parameter needed.

**Eliminated:**
- `_generate_explanations()`
- `regenerate_explanations()`
- API key guard / `model_config` parameter on `evaluate_exam()`

**Preserved:**
- `_determine_level()`
- `_save_feedback_markdown()` / `resave_feedback_markdown()`
- `append_to_tracking()`

### `tools/question_bank.py`

**`cache_contexts()`** — Preserves explanations in `questions_json`. Currently hardcodes `"explanation": None` in the stored questions loop (line 88). Change to `"explanation": q.get("explanation")` to preserve the AI-generated explanations.

**`prefill_bank()`** — New flow:
1. `generate_exam()` (questions + explanations)
2. `review_exam_quality()` (unified review)
3. Drop contexts with critical flags (deterministic only)
4. Cache remaining: clean → `reviewed`, has warnings → `warned`
5. Success message includes warned count

**`get_bank_stats()`** — Returns `warned` count alongside `reviewed` and `battle_tested`.

**`assemble_exam_from_cache()`** — Both per-type SQL queries (fill_in_blank and error_identification) get the new ORDER BY clause. The SELECT statements must also add `status` and `user_flags` to the column list so they're available to `_build_exam_from_rows()`. The new ordering:
```sql
SELECT context_id, type, passage, questions_json, num_questions, grammar_topics, status, user_flags
FROM contexts WHERE type = '...'
ORDER BY
  CASE WHEN user_flags >= 1 THEN 1 ELSE 0 END,
  CASE status
    WHEN 'battle_tested' THEN 0
    WHEN 'reviewed' THEN 1
    WHEN 'warned' THEN 2
  END,
  times_served ASC,
  RANDOM()
```

`_select_contexts_evenly()` receives pre-sorted rows so its greedy selection naturally prefers higher-quality contexts when topic counts are equal.

**`_build_exam_from_rows()`** — Reads `status` from the row tuple and passes it as `bank_status` field in each assembled context dict.

**`upgrade_to_battle_tested()`** — Simplified. No longer attaches explanations (already present). Just flips status. The SQL WHERE clause must be updated from `status = 'reviewed'` to `status IN ('reviewed', 'warned')` to allow warned contexts to also be battle-tested.

**New function: `flag_context()`** — Increments `user_flags` for a context matched by `bank_context_id` or `passage_hash`. Also logs the flag details (category, free-text) to `system_error_tracking.md` for visibility.

### `app.py`

**Setup screen:**
- Bank stats display includes warned count: "42 questions (24 battle-tested, 12 reviewed, 6 warned)"
- Pre-fill success message: "Cached 18 questions from 9 contexts (2 warned)"

**Exam screen:**
- Info banner if exam contains warned contexts: "Some questions in this exam were flagged with minor quality warnings during generation. They may contain ambiguities."
- Per-context "Flag quality issue" button with category dropdown + optional free-text. Category and free-text are logged to `system_error_tracking.md` via `flag_context()`. The `user_flags` integer counter in the DB tracks the count; the detailed feedback lives in the tracking file.

**Results screen:**
- Per-context caption for warned questions: "This question was flagged during quality review (warning)"
- Explanation-related flags (e.g., `incorrect_rule`, `hallucinated_rule`) from the unified exam review are surfaced on the results page using the same `flagged_questions` list stored in session state. The existing `flagged_expl_ids` logic is replaced: instead of reading from the eliminated `feedback_review`, it reads explanation-category flags from the unified `exam_review` result.
- No change to score display, level, or explanation rendering

**Evaluation flow in app.py:**
- Remove API key requirement for evaluation step
- Remove feedback review step (`review_feedback_quality()` call and related imports)
- Remove explanation regeneration logic (`regenerate_explanations()` call and related imports)
- Remove `feedback_review` session state variable and related logic
- Scoring becomes: compare answers → display pre-generated explanations → save markdown

## Assembly Logic Detail

The `_select_contexts_evenly()` function continues to handle grammar topic distribution. The new SQL ordering feeds it rows in quality-preference order, so higher-quality contexts are selected first when topic counts are equal.

Fallback behavior: if there aren't enough high-quality contexts, lower-quality ones (warned, user-flagged) are used. A complete exam with some warned contexts is better than no exam.

## Edge Cases

### Pre-fill with all contexts warned
Success — all contexts cache as `warned`. Message: "Cached 18 questions from 9 contexts (9 warned)."

### Pre-fill with all contexts critical (deterministic failures)
Failure — same as today. Message: "All generated contexts had critical quality issues. Try again." This should be very rare since only duplicate options and structural mismatches are critical.

### User flags a battle-tested context
The `user_flags` counter increments. The context keeps its `battle_tested` status but gets deprioritized in assembly. It's not removed from the cache.

### Existing database with old data
Old contexts without `user_flags` column get default 0 via `ALTER TABLE ADD COLUMN`. Old contexts with `explanation: null` in `questions_json` continue to work — the results page already handles null explanations gracefully.

### Cached exam from before this change (no explanations)
Old `reviewed` contexts with `explanation: null` in `questions_json` are legacy data. When served, the results page shows the score without explanations (it already handles null explanations gracefully). These contexts can still be battle-tested — `upgrade_to_battle_tested()` just flips status. Over time, users can delete and rebuild the cache via the existing "delete bank" button, which replaces old data with new contexts that include explanations. No automatic backfill or legacy fallback code is needed.

## Migration

1. Add `user_flags` column: `ALTER TABLE contexts ADD COLUMN user_flags INTEGER NOT NULL DEFAULT 0`
2. Run in `init_db()` — safe to run multiple times (check if column exists first via `PRAGMA table_info(contexts)`)
3. No data migration needed — existing contexts keep their current status and null explanations
4. Users who want explanations on old cached contexts can delete and re-fill the bank
