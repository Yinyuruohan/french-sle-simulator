# LLM Grader — Expert Review Interface

A standalone web application for subject-matter experts to review AI-generated exam content, provide structured ratings, and annotate outputs. Supports quality assurance for the exam generation pipeline.

## Architecture

Flask backend serving a REST API + static HTML/CSS/JS SPA frontend. Separate from the Streamlit simulator but shares the `tools/` layer and `question_bank.db`.

### File Structure

```
grader/
  app.py              # Flask app: REST API endpoints + static file serving
  static/
    index.html         # SPA entry point (list + detail views, hash-based routing)
    style.css          # Grader styles (Plus Jakarta Sans, blue palette from simulator)
    app.js             # Vanilla JS: API calls, view rendering, state management
tools/
  grader_db.py         # Reviews table: init, CRUD, filtered queries
  question_bank.py     # Existing — read-only from grader
question_bank.db       # Shared SQLite — adds `reviews` table
```

### How It Runs

- `python grader/app.py` starts Flask on port 5001
- Flask serves the SPA at `/` and the API at `/api/*`
- The Streamlit simulator continues independently on port 8501

### Boundaries

- `tools/grader_db.py` owns all reviews table operations; Flask never writes SQL directly
- `tools/question_bank.py` is read-only from the grader — queries contexts, never modifies them
- The SPA talks exclusively to `/api/*` endpoints

## Database Schema

A `reviews` table added to the existing `question_bank.db`:

```sql
CREATE TABLE IF NOT EXISTS reviews (
    context_id TEXT PRIMARY KEY,
    model_output TEXT NOT NULL,
    expert_rating TEXT,
    expert_critique TEXT,
    llm_evaluator_rating TEXT,
    llm_evaluator_critique TEXT,
    agreement INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### Column Details

| Column | Type | Description |
|--------|------|-------------|
| context_id | TEXT PK | Same UUID from `contexts` table — one review per context |
| model_output | TEXT | JSON snapshot of full context data at review creation time |
| expert_rating | TEXT | `'Good'` or `'Bad'` (NULL = not yet reviewed) |
| expert_critique | TEXT | Free-text annotation (NULL = not yet reviewed) |
| llm_evaluator_rating | TEXT | `'Good'` or `'Bad'` (NULL — populated by future feature) |
| llm_evaluator_critique | TEXT | LLM-generated critique (NULL — populated by future feature) |
| agreement | INTEGER | 0 or 1 (NULL — populated by future batch job) |
| created_at | TEXT | ISO timestamp of first review creation |
| updated_at | TEXT | ISO timestamp of last edit |

### model_output JSON Structure

```json
{
  "context_id": "uuid",
  "type": "fill_in_blank",
  "passage": "...",
  "questions": [
    {
      "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
      "correct_answer": "B",
      "grammar_topic": "preposition",
      "explanation": {"why_correct": "...", "grammar_rule": "..."}
    }
  ],
  "grammar_topics": "preposition",
  "status": "reviewed"
}
```

The snapshot is taken when the review record is first created (on first detail view access). This makes reviews durable — they retain the exact content that was reviewed even if the context is later deleted or modified.

### Data Layer — `tools/grader_db.py`

Functions:

- `init_reviews_table()` — create table if not exists
- `get_contexts_for_review(filters)` — query `contexts` table with optional filters (status, user_flags, has_review), left-joined with `reviews` to include review status. Returns list of summary dicts.
- `get_or_create_review(context_id)` — fetch existing review or create one by snapshotting the context from the `contexts` table. Returns full review dict.
- `save_review(context_id, expert_rating, expert_critique)` — upsert rating and critique, update `updated_at`. Returns updated timestamp.
- `get_filtered_context_ids(filters)` — returns ordered list of context_ids matching current filters. Used by sidebar navigator and Prev/Next.

## REST API

Four endpoints under `/api/`:

### GET /api/contexts

List view data with optional filters (all combinable).

**Query params:**
- `status` — `battle_tested`, `reviewed`, or `warned`
- `flagged` — `true` (user_flags >= 1) or `false` (user_flags == 0)
- `reviewed` — `true` (has expert review) or `false` (no review yet)

**Response:**
```json
[
  {
    "context_id": "uuid",
    "status": "reviewed",
    "user_flags": 0,
    "expert_rating": "Good"
  }
]
```

### GET /api/contexts/{context_id}

Single-item detail data. Creates the review record + model_output snapshot on first access if one doesn't exist yet.

**Response:**
```json
{
  "context_id": "uuid",
  "model_output": { "..." },
  "expert_rating": "Good",
  "expert_critique": "...",
  "llm_evaluator_rating": null,
  "llm_evaluator_critique": null,
  "agreement": null
}
```

### PUT /api/contexts/{context_id}/review

Submit or update an expert review.

**Request body:**
```json
{
  "expert_rating": "Good",
  "expert_critique": "Optional text"
}
```

**Response:**
```json
{
  "success": true,
  "updated_at": "2026-04-11T..."
}
```

**Validation:** `expert_rating` must be `"Good"` or `"Bad"`. Returns 400 otherwise.

### GET /api/contexts/{context_id}/neighbors

Previous/Next navigation within the filtered list.

**Query params:** same as `GET /api/contexts`

**Response:**
```json
{
  "previous": "uuid",
  "next": "uuid"
}
```

Returns null for `previous`/`next` when at the start/end of the filtered list.

**Error handling:** All endpoints return JSON. 404 for unknown context_id, 400 for invalid params.

## Frontend

### SPA Routing

Hash-based routing, no build step:
- `#/` — List view
- `#/review/<context_id>` — Single-item review view

### List View

Three filters at the top (Status, User Flags, Reviewed) — all dropdowns, combinable. No pagination — full scrollable list (adequate for current ~30 contexts; add pagination when bank exceeds ~100).

Table columns:
- **Context ID** — truncated UUID (first 8 chars), monospace
- **Status** — color-coded badge (green=battle_tested, blue=reviewed, yellow=warned)
- **Flags** — count, red when > 0
- **Review** — "Good"/"Bad" badge or "not reviewed" in gray italic

Clicking a row navigates to `#/review/<context_id>`.

### Single-Item Review View

Three-column layout:

**Left — Context navigator sidebar** (180px, sticky):
- Scrollable list of context IDs (truncated) from the filtered set
- Annotation indicator per item: green filled dot = reviewed, empty gray circle = not reviewed
- Currently selected item highlighted with blue background + blue left border
- Click any item to load it without returning to list view
- Respects same active filters

**Middle — Exam content:**
- Context passage (French text with blanks or error segments)
- Questions with options (correct answer highlighted green)
- Grammar topic as inline metadata
- Explanation (why_correct + grammar_rule)

**Right — Review panel:**
- Good/Bad toggle buttons (selected state: green border for Good, red for Bad)
- Free-text critique textarea (pre-populated if review exists)
- Submit/Update button (labeled "Update" when review exists)
- LLM Evaluator section (read-only): shows rating + critique when available, "Not yet evaluated" when NULL
- Back to list link

**Navigation:**
- Previous/Next buttons at top with "N of M" counter
- Sidebar click for direct access
- All navigation respects active filters

### State Management

Vanilla JS module:
- `filters` — current selections, persisted to `sessionStorage`
- `contextList` — cached array of context_ids from last list fetch, shared by sidebar and Prev/Next
- `currentContextId` — active context in review view

Flow:
1. List view loads → filters from `sessionStorage` → fetch `GET /api/contexts` → render table
2. Filter change → update `sessionStorage` → re-fetch → re-render
3. Row click → `#/review/<id>` → fetch detail + render sidebar from cached `contextList`
4. Sidebar/Prev/Next click → update hash → fetch new detail → re-render middle + right
5. Review submit → `PUT` → update sidebar dot immediately → stay on view
6. Back to list → `#/` → re-fetch with current filters

### Styling

- Plus Jakarta Sans font family (matches simulator)
- Blue palette (#2563eb primary, #f0f6ff background)
- Color-coded badges consistent with simulator's design system
- Responsive within reasonable desktop widths (not mobile-optimized)

## Out of Scope

- Authentication / reviewer identity tracking
- LLM evaluator — columns created but always NULL
- Agreement computation — column created but always NULL
- Pagination — not needed at current scale
- Mobile responsiveness
- Question type and grammar topic filters (visible as metadata in detail view only)