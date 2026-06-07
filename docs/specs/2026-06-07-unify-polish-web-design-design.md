# Design: Unify & Polish the SLE Web App

**Date:** 2026-06-07
**Status:** Approved (pending implementation plan)

## Objective

The app has three features that today feel like separate products: **Writing Expression** and **Reading Comprehension** share one Streamlit app and design system, while **Flashcards** is a disconnected React/Flask app on port 5002, reached via a small link button. There is no single home that presents all three as equal entry points.

Goal: make the three features read as **one cohesive product** (unify) and **raise the visual quality** uniformly (polish), without rewriting any feature.

## Confirmed Decisions

- **Direction:** unify *and* polish.
- **Architecture:** keep the two servers (Streamlit for Writing+Reading, React/Flask for Flashcards). Unify via a shared visual shell, not a rewrite.
- **Home layout:** marketing hero + three equal door-cards. Marketing extras (mock-UI preview, feature cards) are **removed** — the home is hero + 3 doors only.
- **Visual identity:** refine the existing light/federal blue theme (`#2563eb`, Plus Jakarta Sans). No dark/premium redesign, no new palette.

## Components

### 1. Shared top nav bar

A slim top bar on every screen across both servers:
`🇨🇦 SLE Prep` (logo → home) · **Writing** · **Reading** · **Flashcards**, current section highlighted.

- **Streamlit (Writing + Reading):** new helper `_render_top_nav(active: str)` in `tools/streamlit_design.py`, injected as HTML with real `<a>` links:
  - Logo → app root (`/`), which shows the home page.
  - Writing → app root with a query param (`/?goto=writing`). `app.py` reads this on load and jumps straight into the writing setup stage, so "Writing" is distinct from the logo/home link. Without the param, app root shows the home.
  - Reading → the RC page path (its own Streamlit page URL — already unambiguous).
  - Flashcards → `http://localhost:5002`.
  - Hide Streamlit's default auto-generated page nav (`[data-testid="stSidebarNav"]`) so there is exactly one nav.
- **Flashcard (React):** a matching `<TopNav>` component added above the existing layout in `flashcard/src/App.jsx`. The existing left sidebar (Dashboard / Progress / Vocab Inbox) stays for **intra-app** navigation; the top bar handles **cross-app** navigation back to Writing/Reading (and home).

Links are plain navigation — no shared session state between servers.

**Interface:** `_render_top_nav(active)` — `active` is one of `"home" | "writing" | "reading"`; renders the bar and highlights the active item (Writing is active once the user is past the home/setup into the writing flow). Depends only on Streamlit's HTML injection. `<TopNav active="flashcards">` — pure presentational React component; depends on the same color/font tokens as the CSS.

### 2. Unified home page

Rework `render_welcome()` in `app.py`:
- Keep the hero (badge, headline, subtitle) but reframe copy from writing-only to the full suite (e.g. "Practice French for the SLE, end to end" · "Writing · Reading · Vocabulary").
- Below the hero: **three equal door-cards** (Writing / Reading / Flashcards), each with icon, one-line description, and a CTA. Writing/Reading enter their Streamlit flows; Flashcards links to port 5002.
- **Remove** the existing mock-UI preview block and the "Core Features" card grid.
- The shared top nav bar renders at the top with `active="home"`.

### 3. Refined visual system

Tokens already live in `inject_design_system()` in `tools/streamlit_design.py`. Refinements, applied uniformly to home, Writing, and Reading:
- Consistent spacing and radius scale (e.g. 8 / 12 / 16 / 24 px; cards 12px radius).
- One reusable door-card / feature-card treatment, used on the home page.
- Tighter visual hierarchy on the Reading page (passage vs. question vs. options) and on result screens.
- Keep the `#2563eb` accent and Plus Jakarta Sans throughout.

### 4. Flashcard restyle to match

- Update `flashcard/src/index.css` so the React app uses the same blue/Jakarta tokens (replacing its current standalone "Lexique" styling where it diverges).
- Add the shared `<TopNav>`.
- Rebuild the committed Vite output (`flashcard/static/dist/`) so the server works without Node tooling.

## Data Flow

No new data flow. Cross-app navigation is via URLs only. No new APIs, no shared session, no progress aggregation.

## Scope Guardrails (YAGNI)

**In scope:** shared top nav bar, unified home (hero + 3 doors), refined design tokens applied across all Streamlit screens, flashcard restyle + rebuild.

**Out of scope:**
- Progress-dashboard home (would require cross-feature stats plumbing).
- Dark/premium identity or any new palette.
- Rewriting flashcard into Streamlit or merging the two servers.
- Any change to exam generation, grading, question-bank, or timer logic.

## Error Handling

- The Flashcards link points to `http://localhost:5002`; if that server is not running the browser shows its standard connection error. This matches today's behavior — no new handling added.
- Top nav must degrade gracefully if injected before Streamlit finishes rendering (same pattern as the existing `inject_design_system()` HTML injection).

## Testing / Verification

- All existing tests must still pass — especially `tests/test_rc_timer.py` (the timer HTML is **not** touched by this work).
- Manual verification: launch all three (`streamlit run app.py`, `python flashcard/app.py`), confirm:
  - The top nav bar appears on home, Writing, Reading, and Flashcards.
  - Each nav link routes correctly in all directions.
  - The home page shows hero + 3 doors only (no mock-UI / feature grid).
  - Colors, fonts, spacing read as one product across all three features.
