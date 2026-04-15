# LLM Grader — Expert Review Interface Workflow SOP

## Objective

Provide subject-matter experts with a web interface to review AI-generated exam content, assign structured ratings (Good/Bad), and annotate outputs with free-text critique. Supports quality assurance for the exam generation pipeline.

## Required Inputs

- A populated `question_bank.db` with contexts (generated via the exam simulator workflow)
- Python with Flask installed (`pip install -r requirements.txt`)

## Tools Used

| Tool | Purpose |
|---|---|
| `grader/app.py` | Flask application: REST API endpoints + static SPA serving |
| `grader/batch.py` | Batch Excel export (`export_to_excel`) and import (`import_from_excel`) |
| `tools/grader_db.py` | Reviews table: init, CRUD, filtered queries, snapshot staleness detection |
| `tools/question_bank.py` | Read-only access to contexts table for live data |

## How to Run

```bash
python grader/app.py
```

Then open `http://localhost:5001` in a browser.

**Port configuration:**
- Default: 5001
- Override via environment variable: `GRADER_PORT=5002 python grader/app.py`
- Override via CLI argument: `python grader/app.py --port 5002`

## Architecture

- Flask backend with `create_app()` factory pattern
- REST API under `/api/*` — 5 endpoints (list, detail, review, export, import)
- Static SPA frontend served at `/` (vanilla HTML/CSS/JS, no build step)
- Shares `question_bank.db` with the Streamlit simulator
- Writes only to the `reviews` table; never modifies the `contexts` table
- Batch module (`grader/batch.py`) handles Excel formatting via `openpyxl`; `COLUMNS` list is the single source of truth for column schema

## Workflow Steps

1. **Startup** — Flask initializes the `reviews` table (if not exists) and cleans up empty review records (expert_rating IS NULL)
2. **List view** — Expert sees all contexts in a filterable table:
   - Filter by status (battle_tested, reviewed, warned)
   - Filter by user flags (flagged / unflagged)
   - Filter by review state (reviewed / not reviewed)
   - Clicking a row navigates to the detail view
3. **Detail view** — Three-column layout:
   - **Left sidebar** — Scrollable navigator with "Fill-in #N" / "Error-ID #N" labels and review status dots (green = reviewed, gray = not reviewed)
   - **Center** — Context passage, questions with correct answer highlighted, grammar topic, and explanations (why_correct + grammar_rule)
   - **Right panel** — Good/Bad rating toggle, free-text critique textarea, Submit/Update button, LLM Evaluator section (read-only, currently shows "Not yet evaluated")
4. **Review submission** — Expert selects Good or Bad, optionally writes critique, clicks Submit:
   - First submission creates a JSON snapshot of the context (`model_output`) for durability
   - Subsequent submissions update rating/critique without changing the snapshot
   - Sidebar dot updates optimistically; reverts on failure
   - Toast notification confirms success or shows error
5. **Navigation** — Previous/Next buttons + sidebar clicks allow moving through contexts without returning to list view. All navigation respects active filters.
6. **Snapshot staleness** — If a context is regenerated after its review snapshot was taken, the detail view displays a "Snapshot outdated" banner. Detection uses SHA-256 hash comparison of passage + questions + grammar_topics.
7. **Batch export** — Expert clicks "↓ Download Excel" in the list view:
   - Active filters are forwarded to `GET /api/export` as query parameters
   - `export_to_excel()` builds one row per question; context-level fields repeat across rows
   - Editable cells (`expert_rating`, `expert_critique`) are yellow and unlocked on the first row of each context; all other cells are grey and locked
   - `expert_rating` column has a dropdown constraint: only "Good" and "Bad" are accepted
   - File is named `grader_export_YYYY-MM-DD.xlsx`
8. **Batch import** — Expert clicks "↑ Upload Excel" and selects a filled-in file:
   - File is posted to `POST /api/import`
   - `import_from_excel()` reads the first row of each contiguous context block; subsequent question rows are skipped
   - Blank ratings are skipped (counted as `skipped`); invalid ratings are collected as errors
   - Successfully parsed rows call `save_review()` — same path as single-context review submission
   - List view refreshes automatically; a toast shows imported/skipped/error counts
   - Detailed per-context errors appear inline below the upload button

## Data Model

### Reviews Table

| Column | Type | Description |
|--------|------|-------------|
| context_id | TEXT PK | Same UUID from contexts table |
| model_output | TEXT | JSON snapshot of context at review time |
| expert_rating | TEXT | 'Good' or 'Bad' (NULL = not yet reviewed) |
| expert_critique | TEXT | Free-text annotation |
| llm_evaluator_rating | TEXT | Future: automated LLM rating |
| llm_evaluator_critique | TEXT | Future: automated LLM critique |
| agreement | INTEGER | Future: 0 or 1 (expert vs LLM agreement) |
| created_at | TEXT | ISO timestamp of first review |
| updated_at | TEXT | ISO timestamp of last edit |

No foreign key constraint — reviews must outlive deleted/regenerated contexts since `model_output` is a self-contained snapshot.

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/contexts` | List contexts with optional filters (status, flagged, reviewed) |
| GET | `/api/contexts/{id}` | Context detail + existing review + snapshot_outdated flag |
| PUT | `/api/contexts/{id}/review` | Submit or update expert rating and critique |
| GET | `/api/export` | Download filtered contexts as `.xlsx` for batch review |
| POST | `/api/import` | Upload reviewed `.xlsx` to bulk-save expert ratings |

## Edge Cases

- **Empty question bank** — List view shows empty table; no errors
- **Direct URL access** (`#/review/<id>` bookmark) — SPA fetches unfiltered context list to populate sidebar before loading detail
- **Unknown context_id** — API returns 404 JSON error
- **Invalid rating** — API returns 400 if expert_rating is not "Good" or "Bad"
- **Concurrent use** — Not supported; single-user assumed (SQLite + no auth)
- **Deleted context** — Review persists with its snapshot; staleness check returns None (no banner shown)
- **Filter persistence** — Active filters stored in `sessionStorage`, persist across navigation within the session
- **Export with no results** — `GET /api/export` returns a header-only `.xlsx` (no data rows) when no contexts match the active filters; no error
- **Import with invalid file** — Non-`.xlsx` files return 400; missing `context_id` or `expert_rating` columns return 400 with a descriptive message
- **Import with reordered rows** — Rows are processed as contiguous blocks by `context_id`; if an expert re-sorts the file breaking contiguity, the second occurrence of a `context_id` is treated as a new block and its rating applied
- **Import with unknown context_id** — Rows referencing a `context_id` not in the database are collected as errors and reported in the response; other rows are still processed
- **Partial import** — Import always reports `{"imported": N, "skipped": M, "errors": [...]}` even if some rows fail; the caller sees exactly what succeeded

## Out of Scope

- Authentication / reviewer identity tracking
- Concurrent multi-user editing
- LLM evaluator automation (columns created but always NULL)
- Agreement computation (column created but always NULL)
- Pagination (not needed at current scale of ~30 contexts)
- Mobile responsiveness