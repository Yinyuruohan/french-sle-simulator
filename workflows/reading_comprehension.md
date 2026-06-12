# SLE Reading Comprehension Simulator — Workflow SOP

## Objective

Generate realistic French SLE Reading Comprehension (Compréhension de l'écrit) practice exams — short administrative passages, each with one multiple-choice question — administer them under a countdown timer, grade deterministically, and surface per-question justifications and a stem-family breakdown. Quality assurance is **rule-based** (deterministic Python checks, no LLM reviewer), which makes review free and instantaneous.

This SOP is a sibling of `sle_exam_simulator.md` (Written Expression). Mechanics that are identical there are cross-referenced rather than repeated; the focus here is what RC does differently.

## Required Inputs

- An API key for an OpenAI-compatible model endpoint, configured in `.env` (default: `DEEPSEEK_API_KEY`; RC-specific overrides via `READING_API_KEY/BASE_URL/MODEL`)
- Number of questions (2–30, default 5, chosen at runtime)

## Tools Used

| Tool | Purpose |
|---|---|
| `pages/1_Reading_Comprehension.py` | Streamlit page: 5-stage state machine (`welcome → generating → taking → evaluating → results`) |
| `tools/generate_reading_exam.py` | Generates passages + questions via AI API; validates the response schema before returning |
| `tools/review_reading_exam.py` | Rule-based deterministic reviewer — **no API call** |
| `tools/grade_reading_exam.py` | Deterministic grading + stem-family breakdown — **no API call** |
| `tools/reading_question_bank.py` | SQLite cache (`reading_question_bank.db`): cache reviewed passages, assemble instant exams, prefill |
| `tools/streamlit_design.py` | Shared design system + `_timer_html()` countdown + vocab note sidebar + top nav |

## How to Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open `http://localhost:8501` and click the **Reading Comprehension** door on the home page (or "Reading" in the top nav). The RC page lives under `pages/` so Streamlit auto-discovers it; the default sidebar page list is hidden — the top nav is the navigation surface.

**Model configuration** (`.env`): `READING_API_KEY/BASE_URL/MODEL` override the `DEEPSEEK_API_KEY` default (model `deepseek-v4-pro`). The setup screen's "AI model settings" expander allows per-session model/base-URL overrides.

## Workflow Steps

1. **Setup** (`welcome` stage) — shows bank stats (total / battle-tested / reviewed / warned), a question-count input (2–30), the model settings expander, and a **Prefill bank** button (1 API call: generates N passages, reviews them, caches the survivors — nothing is served to the user).
2. **Source choice** — unlike Written Expression (which checks the cache automatically), RC makes the source explicit. Two buttons:
   - **Instant exam (from bank)** — assembles from cache, 0 API calls; disabled (with tooltip) when unflagged cached questions < N
   - **Generate fresh (API)** — always generates a new exam
3. **Generation** (`generating` stage, fresh path) — `generate_reading_exam(n)` makes 1 API call:
   - One passage per question (1:1 context:question, unlike WE's 1–2 per context)
   - Administrative/workplace French, 15–130 words per passage
   - Each question tagged with a `stem_family` (see Prompt Design below)
   - Each passage labelled with a short French `topic` (e.g. "le recyclage municipal"); the prompt enforces a hard rule that every passage in an exam covers a distinct subject
   - **Topic avoid-list:** the fresh path passes `avoid_topics=get_recent_topics()` (up to 20 most recently cached topics) so new exams steer away from subjects already in the bank — this counters the model's tendency to converge on the same few topics across calls
   - Schema validation rejects malformed responses before they reach the user (valid stem families, vocabulary questions must carry `bolded_term`, non-empty `topic`, etc.)
   - Saves exam markdown to `.tmp/`
4. **Rule-based review + cache split** — `review_reading_exam()` runs deterministic checks (free, instant; see Rule-Based Review below):
   - Contexts with **critical** findings are excluded from the cache
   - Contexts with **warning** findings are cached as `warned`
   - Clean contexts are cached as `reviewed`
   - **Exam-level** warnings (`answer_key_clustering`, `stem_family_overuse`) describe the exam as a whole and do **not** taint individual passages' cache status
   - **The fresh exam is served as-is, including critically-flagged contexts** — the user gets the N questions they asked for; only the bank is selective. There is no regeneration retry (unlike WE).
   - Freshly-cached contexts get `bank_context_id` back-filled so the flag UI works on the results page
5. **Taking** (`taking` stage) — passages rendered with their single question each (radio A–D). A **countdown timer** (90 seconds × N questions) runs as a sticky bar; on expiry a blocking modal stops the attempt (see Timer below). The Vocab Note sidebar (`source='rc'`) saves unknown words to the flashcard inbox, same as in WE. The submit button warns how many questions are unanswered — they count as wrong.
6. **Evaluation** (`evaluating` stage) — `grade_reading_exam()` is fully deterministic, 0 API calls: scores against the answer key, maps to a level (same C/B/A thresholds as WE — see `sle_exam_simulator.md` § Scoring Thresholds), builds the per-stem-family breakdown, saves feedback markdown to `.tmp/`, appends errors to `user_error_tracking.md`. Post-evaluation bank maintenance mirrors WE: `upgrade_to_battle_tested()` promotes clean `reviewed` contexts; `update_last_incorrect()` records misses.
7. **Results** (`results` stage) — score / percentage / level metrics; per-passage expanders (auto-expanded for wrong answers) showing all options with the correct answer and the user's answer marked, plus the model-generated **justification**; a per-passage "Flag quality issue" selector (categories: Wrong answer key, Multiple correct answers, Unclear passage, Bad justification, Other — flagged passages are deprioritized in assembly); and a **stem-family breakdown** table (correct/total/% per family) showing which question types need work.

## Generation Prompt Design

Each question is tagged with one of 10 **stem families** (the repertoire is flexible — the prompt treats it as a menu, not a quota):

`detail_comprehension`, `intent_purpose`, `faux_fausse`, `main_idea`, `vocabulary`, `best_title`, `sentence_completion`, `source_identification`, `inference`, `vraie_not_purpose`

Structural contracts enforced by schema validation and/or review:

- **`vocabulary`** questions must carry a non-null `bolded_term`; the term must appear as `**term**` in the passage and be repeated in the question text. All other families must have `bolded_term = null`.
- **`sentence_completion`** passages must end with a `____.` blank.
- **`has_signature`** — passages may carry a memo-style signature block only when the genre naturally calls for it (the prompt forbids forcing them); the flag is stored in the bank.
- **`topic`** — every passage carries a short French noun-phrase label (2–6 words) naming its subject; must be non-empty (schema validation). The prompt forbids two passages on the same subject within one exam, and the caller can pass `avoid_topics` (recently used topics) to exclude across exams.
- Passage length 15–130 words (checked at review as a warning).

## Rule-Based Review (no LLM)

`review_reading_exam()` returns the same `{"flagged_questions": [...]}` shape as the WE reviewer so the bank orchestration code is shared, but every check is deterministic Python:

| Severity | Category | Check |
|---|---|---|
| Critical | `duplicate_options` | Two or more of A/B/C/D identical (case-insensitive) |
| Critical | `bolded_term_missing_in_passage` | Vocabulary question's `**term**` absent from the passage |
| Critical | `vocab_term_missing_in_stem` | Vocabulary term not repeated in the question text |
| Critical | `sentence_completion_missing_blank` | Passage doesn't end with the `____.` pattern |
| Warning | `word_count_out_of_range` | Passage outside 15–130 words |
| Warning | `option_length_disparity` | Longest option > 3× the shortest (length give-away) |
| Warning (exam-level) | `answer_key_clustering` | One letter is the correct answer in > 70% of questions (only checked when N ≥ 4) |
| Warning (exam-level) | `stem_family_overuse` | Any family appears > ⌈N/3⌉ times (only checked when N ≥ 6) |

Severity semantics: **critical** → excluded from cache; **warning** → cached as `warned`; exam-level warnings → logged but don't affect any passage's cache status. No regeneration retry in either path.

Because the reviewer can't judge French semantics, it validates structure only — answer-key correctness is *not* verified (see Known Limitations).

## Question Bank

The lifecycle is the same as WE (`sle_exam_simulator.md` § Unified Quality Review: `reviewed` → `battle_tested` after a clean serving; `warned` is permanent; user flags deprioritize). RC-specific differences:

- Separate database: `reading_question_bank.db` (gitignored, deletable/rebuildable)
- Exactly 1 question per context
- Schema stores `stem_family` (instead of WE's `grammar_topics`), `has_signature`, and `topic` (the passage's subject label; `get_recent_topics()` reads it to build the avoid-list for fresh generation; older DBs are migrated in place with an empty topic)
- Assembly ordering: `times_served` ASC first (fresh material always surfaces before repeats — a passage only repeats once the whole bank has been cycled), then a single quality tier (`reviewed` > `battle_tested` > `warned` > user-flagged), then `RANDOM()` tiebreak. No stem-family balancing. The selected contexts are shuffled before numbering, so exam order is random rather than reflecting selection priority.

## Timer

- Budget: **90 seconds per question** × N, started once on entering the taking stage (`rc_timer_start`, Unix epoch in session state — survives Streamlit reruns)
- Rendered by `tools/streamlit_design.py:_timer_html()` via `st.components.v1.html(height=0)`: the script runs in a same-origin iframe and injects a sticky countdown bar (below Streamlit's toolbar at `top: 60px`) plus a blocking full-screen modal on expiry into `window.parent.document`
- **Implementation constraint:** `st.html()` strips `<script>` tags — JS must go through `st.components.v1.html()`

## API Call Summary

| Action | Calls |
|---|---|
| Generate fresh exam | 1 |
| Rule-based review | 0 |
| Grading | 0 |
| **Total (fresh exam)** | **1** |
| **Total (instant exam from bank)** | **0** |
| Prefill bank | 1 |

(WE needs 2 calls per fresh exam because its reviewer is an LLM; RC needs 1.)

## Output Files

| File | Location | Persistence |
|---|---|---|
| Exam markdown | `.tmp/` | Disposable |
| Feedback markdown | `.tmp/` | Disposable |
| User error tracking | `user_error_tracking.md` | Persistent (append-only, shared with WE) |
| RC question bank | `reading_question_bank.db` | Persistent (SQLite cache, can be deleted and rebuilt) |

## Known Limitations

- The rule-based reviewer validates **structure only** — it cannot verify that the marked answer is actually correct, that distractors are wrong, or that the passage is grammatically sound. Bad answer keys reach the user; the per-passage flag UI is the recovery path.
- Fresh exams are served unfiltered: a critically-flagged passage (e.g., duplicate options) still appears in the exam that triggered the flag — it is only excluded from the *cache*.
- The timer is client-side JavaScript. A page refresh restores the correct remaining time (state lives in `rc_timer_start` server-side), but the blocking modal can be bypassed by anyone with dev tools — it's an honor-system simulation, not enforcement.
- Justifications are generated together with the questions and are not independently reviewed.
- The 90 s/question budget approximates the official pacing but is not the PSC's actual timing model.
- Topic diversity is prompt-enforced, not verified: the reviewer has no topic-overlap check, and the avoid-list only knows topics that reached the bank (passages excluded for critical issues leave no trace). Rows cached before the `topic` column existed have an empty topic and never appear in the avoid-list.

## Future Improvements

- Optional LLM spot-review of cached `warned` passages (would restore answer-key verification at 1 extra call)
- Difficulty targeting (A/B/C level passages)
- Per-stem-family practice mode (drill only `inference`, etc.)
- Progress dashboard over `user_error_tracking.md` history
