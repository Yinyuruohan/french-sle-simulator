# Unify & Polish Web Design — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Writing, Reading, and Flashcards read as one product via a shared top nav bar and a unified home (hero + 3 equal doors), with refined design tokens applied across all screens.

**Architecture:** Keep the two servers (Streamlit for Writing+Reading on :8501, React/Flask for Flashcards on :5002). Unify visually with a self-contained HTML nav bar injected on every Streamlit screen and a matching React `<TopNav>`. Cross-app navigation is plain `<a>` links — no shared session. The Writing nav link uses `/?goto=writing` so it lands in the writing flow rather than just the home.

**Tech Stack:** Streamlit (Python), `st.html()` for HTML/CSS injection (no JS — pure anchors), React 18 + Vite 5 (committed build output).

**Note on flashcard scope (discovered during planning):** `flashcard/src/index.css` *already* uses the same tokens (`--primary: #2563eb`, `--bg: #f0f6ff`, Plus Jakarta Sans) as the Streamlit design system. So the flashcard work is **only** adding the shared top nav + its CSS — there is no broad restyle to do. This narrows the spec's "flashcard restyle" task accordingly.

---

### Task 1: `_render_top_nav()` helper

**Files:**
- Modify: `tools/streamlit_design.py` (add function + module constant near top)
- Test: `tests/test_top_nav.py` (create)

Mirrors the existing `_timer_html()` pattern: a pure function returning an HTML string, unit-tested by asserting on the string. The bar is rendered with `st.html()` (inline, sanitized HTML — anchors navigate the top window; no JS needed).

- [ ] **Step 1: Write the failing test**

Create `tests/test_top_nav.py`:

```python
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.streamlit_design import _render_top_nav


def test_nav_has_three_sections():
    html = _render_top_nav("home")
    assert ">Writing<" in html
    assert ">Reading<" in html
    assert ">Flashcards<" in html


def test_nav_writing_link_uses_goto():
    assert 'href="/?goto=writing"' in _render_top_nav("home")


def test_nav_reading_link_to_page():
    assert 'href="/Reading_Comprehension"' in _render_top_nav("home")


def test_nav_flashcards_external():
    assert "http://localhost:5002" in _render_top_nav("home")


def test_nav_active_highlight_reading():
    html = _render_top_nav("reading")
    assert 'class="sle-nav-link active" href="/Reading_Comprehension"' in html


def test_nav_active_highlight_writing():
    html = _render_top_nav("writing")
    assert 'class="sle-nav-link active" href="/?goto=writing"' in html


def test_nav_hides_sidebar_pagelist():
    assert "stSidebarNav" in _render_top_nav("home")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_top_nav.py -v`
Expected: FAIL — `ImportError: cannot import name '_render_top_nav'`.

- [ ] **Step 3: Write minimal implementation**

In `tools/streamlit_design.py`, add a module constant after the imports (near the top, below the `from tools.flashcard_db import add_to_inbox` line):

```python
FLASHCARD_URL = "http://localhost:5002"
```

Then add this function (place it directly above `def _render_vocab_note_sidebar`):

```python
def _render_top_nav(active: str = "home") -> str:
    """Return self-contained HTML for the shared top navigation bar.

    `active` is one of "home" | "writing" | "reading" and controls which
    item is highlighted. Rendered inline via st.html() — pure HTML/CSS, no
    JS. Also hides Streamlit's auto-generated sidebar page list so there is
    exactly one navigation surface.
    """
    def cls(name: str) -> str:
        return "sle-nav-link active" if name == active else "sle-nav-link"

    return f"""
    <style>
      [data-testid="stSidebarNav"] {{ display: none !important; }}
      .sle-topnav {{
        display: flex; align-items: center; gap: 22px;
        background: #ffffff; border: 1px solid #e2e8f0;
        border-radius: 12px; padding: 12px 20px; margin-bottom: 20px;
        box-shadow: 0 2px 8px rgba(37,99,235,0.06);
        font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
      }}
      .sle-topnav .sle-brand {{
        font-weight: 800; font-size: 15px; color: #0f172a;
        text-decoration: none; margin-right: auto; letter-spacing: -0.02em;
      }}
      .sle-topnav .sle-nav-link {{
        font-weight: 600; font-size: 14px; color: #64748b;
        text-decoration: none; padding: 6px 2px;
        border-bottom: 2px solid transparent; transition: color .15s;
      }}
      .sle-topnav .sle-nav-link:hover {{ color: #2563eb; }}
      .sle-topnav .sle-nav-link.active {{
        color: #2563eb; border-bottom-color: #2563eb;
      }}
    </style>
    <div class="sle-topnav">
      <a class="sle-brand" href="/" target="_self">🇨🇦 SLE Prep</a>
      <a class="{cls('writing')}" href="/?goto=writing" target="_self">Writing</a>
      <a class="{cls('reading')}" href="/Reading_Comprehension" target="_self">Reading</a>
      <a class="sle-nav-link" href="{FLASHCARD_URL}" target="_blank">Flashcards</a>
    </div>
    """
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_top_nav.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add tools/streamlit_design.py tests/test_top_nav.py
git commit -m "feat: add shared top nav bar HTML helper"
```

---

### Task 2: `?goto=writing` stage resolver

**Files:**
- Modify: `app.py` (add pure helper near `go_to`, wire into router at bottom)
- Test: `tests/test_app_nav.py` (create)

Extract the decision as a pure function so it's unit-testable; the router applies it with the Streamlit side effects.

- [ ] **Step 1: Write the failing test**

Create `tests/test_app_nav.py`:

```python
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import _resolve_initial_stage


def test_goto_writing_from_welcome_enters_setup():
    assert _resolve_initial_stage("welcome", {"goto": "writing"}) == "setup"


def test_no_param_keeps_welcome():
    assert _resolve_initial_stage("welcome", {}) == "welcome"


def test_goto_does_not_override_midflow():
    assert _resolve_initial_stage("results", {"goto": "writing"}) == "results"


def test_unknown_goto_value_ignored():
    assert _resolve_initial_stage("welcome", {"goto": "nope"}) == "welcome"
```

> Note: importing `app` executes its module body (it calls `st.set_page_config`, `init_db()`, and the router). This matches how `tests/test_generate_exam.py` already imports tool modules; if import side effects cause a failure under pytest, wrap the router block at the bottom of `app.py` in `if __name__ == "__main__":` is NOT needed — Streamlit needs it at import. Instead, the test only imports the pure function, and Streamlit's `st.*` calls are no-ops outside a running server. If `st.set_page_config` raises, add `import streamlit as st` guard is unnecessary — verify in Step 2 and, if it fails, move `_resolve_initial_stage` into `tools/streamlit_design.py` instead and import from there (same test asserts, different import path).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_app_nav.py -v`
Expected: FAIL — `ImportError: cannot import name '_resolve_initial_stage'`.

- [ ] **Step 3: Write minimal implementation**

In `app.py`, add this function right after the `go_to` function (around line 51):

```python
def _resolve_initial_stage(current_stage, query_params):
    """Jump into the writing setup stage when the user arrives via the
    top-nav Writing link (?goto=writing) from the welcome page. Mid-flow
    stages are never overridden."""
    if current_stage == "welcome" and query_params.get("goto") == "writing":
        return "setup"
    return current_stage
```

Then wire it into the router. Replace the router block at the bottom of `app.py`:

```python
stage = st.session_state.stage
```

with:

```python
_resolved = _resolve_initial_stage(st.session_state.stage, st.query_params)
if _resolved != st.session_state.stage:
    st.session_state.stage = _resolved
    if "goto" in st.query_params:
        del st.query_params["goto"]
stage = st.session_state.stage
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_app_nav.py -v`
Expected: PASS (4 passed). If the import raised in Step 2 due to Streamlit side effects, apply the fallback noted in Step 1 (move the function to `tools/streamlit_design.py` and update both the import in the test and the call in `app.py`), then re-run.

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_app_nav.py
git commit -m "feat: route ?goto=writing into the writing setup stage"
```

---

### Task 3: Render the top nav on Streamlit screens

**Files:**
- Modify: `app.py` (import + inject in router)
- Modify: `pages/1_Reading_Comprehension.py` (import + inject after design system)

No unit test — this is rendering wiring, verified manually in Task 6. The nav is an in-flow block (not fixed) injected as the first element so it sits at the top without fighting Streamlit's header.

- [ ] **Step 1: Update the app.py import**

In `app.py`, change:

```python
from tools.streamlit_design import inject_design_system, _render_vocab_note_sidebar
```

to:

```python
from tools.streamlit_design import inject_design_system, _render_vocab_note_sidebar, _render_top_nav
```

- [ ] **Step 2: Inject the nav in the router**

In `app.py`, immediately after the `stage = st.session_state.stage` line (from Task 2) and before the `if stage == "welcome":` dispatch, add:

```python
st.html(_render_top_nav("home" if stage == "welcome" else "writing"))
```

- [ ] **Step 3: Inject the nav on the Reading page**

In `pages/1_Reading_Comprehension.py`, update the import:

```python
from tools.streamlit_design import inject_design_system, _timer_html, _render_vocab_note_sidebar
```

to:

```python
from tools.streamlit_design import inject_design_system, _timer_html, _render_vocab_note_sidebar, _render_top_nav
```

Then directly after the existing `inject_design_system()` call (around line 38), add:

```python
st.html(_render_top_nav("reading"))
```

- [ ] **Step 4: Verify the existing suite still passes**

Run: `python -m pytest tests/ -q`
Expected: PASS (all existing tests, plus the new nav tests).

- [ ] **Step 5: Commit**

```bash
git add app.py pages/1_Reading_Comprehension.py
git commit -m "feat: render shared top nav on writing and reading screens"
```

---

### Task 4: Rebuild the home page — hero + 3 doors

**Files:**
- Modify: `app.py` `render_welcome()` (replace mock-UI + feature blocks with door-cards; update hero copy; remove the start button row)

No unit test — layout change verified manually in Task 6.

- [ ] **Step 1: Add door-card CSS**

In `render_welcome()`, inside the big `st.html("""<style>...""")` block, add this CSS just before the closing `</style>` (after the `.lp-features` animation rules near line 435):

```css
      .lp-doors {
        display: flex;
        gap: 14px;
        padding: 24px 40px 8px;
      }
      .lp-door {
        flex: 1;
        display: block;
        background: #fff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 22px 20px;
        text-decoration: none;
        box-shadow: 0 2px 8px rgba(37,99,235,0.06);
        transition: transform .15s, box-shadow .15s, border-color .15s;
      }
      .lp-door:hover {
        transform: translateY(-3px);
        border-color: #93c5fd;
        box-shadow: 0 8px 24px rgba(37,99,235,0.14);
      }
      .lp-door-ic {
        width: 48px; height: 48px;
        border-radius: 12px;
        display: flex; align-items: center; justify-content: center;
        font-size: 24px; margin-bottom: 14px;
      }
      .lp-door h3 {
        font-size: 16px; font-weight: 700; color: #0f172a;
        margin-bottom: 6px;
      }
      .lp-door p {
        font-size: 13px; color: #64748b; line-height: 1.55;
        margin-bottom: 14px;
      }
      .lp-door-cta {
        font-size: 13px; font-weight: 600; color: #2563eb;
      }
```

- [ ] **Step 2: Update the hero copy**

In `render_welcome()`'s HTML, replace the hero headline + subtitle + description block:

```html
          <h1>Practice French writing<br><span class="accent">smarter</span>, not harder</h1>
          <p class="lp-hero-sub">Simulateur d'expression écrite — ÉLS / SLE</p>
          <p class="lp-hero-desc">
            AI-generated practice exams modeled on the official SLE Written Expression format.
            Get instant grammar feedback and track your progress toward levels A, B, and C.
          </p>
```

with:

```html
          <h1>Practice French for the SLE,<br><span class="accent">end to end</span></h1>
          <p class="lp-hero-sub">Simulateur ÉLS / SLE — expression écrite · compréhension de l'écrit · vocabulaire</p>
          <p class="lp-hero-desc">
            One place to practice writing, reading, and vocabulary for the Public Service
            Commission's Second Language Evaluation. AI-generated exams with instant feedback.
          </p>
```

- [ ] **Step 3: Replace the mock-UI + features sections with door-cards**

In `render_welcome()`'s HTML, delete the entire `<!-- Mock UI -->` block (the `<div class="lp-mock">...</div>`, lines ~459-485) **and** the entire `<!-- FEATURES -->` block (`<div class="lp-features">...</div>`, lines ~488-509). In their place, immediately after the closing `</div>` of `.lp-hero-left` and before `<!-- DISCLAIMER -->`, the hero grid no longer needs its second column — close the `.lp-hero` div after `.lp-hero-left`, then add the doors. Concretely, the structure from the badge down to the disclaimer becomes:

```html
      <!-- HERO -->
      <div class="lp-hero" style="grid-template-columns: 1fr;">
        <div class="lp-hero-left">
          <div class="lp-badge">Public Service Commission of Canada</div>
          <h1>Practice French for the SLE,<br><span class="accent">end to end</span></h1>
          <p class="lp-hero-sub">Simulateur ÉLS / SLE — expression écrite · compréhension de l'écrit · vocabulaire</p>
          <p class="lp-hero-desc">
            One place to practice writing, reading, and vocabulary for the Public Service
            Commission's Second Language Evaluation. AI-generated exams with instant feedback.
          </p>
          <div class="lp-pills">
            <span class="lp-pill"><span class="dot"></span>Fill-in-the-blank</span>
            <span class="lp-pill"><span class="dot"></span>Error identification</span>
            <span class="lp-pill"><span class="dot"></span>Timed reading</span>
            <span class="lp-pill"><span class="dot"></span>Spaced-repetition vocab</span>
          </div>
        </div>
      </div>

      <!-- DOORS -->
      <div class="lp-doors">
        <a class="lp-door" href="/?goto=writing" target="_self">
          <div class="lp-door-ic" style="background:#eff6ff;">📝</div>
          <h3>Writing Expression</h3>
          <p>AI-generated exams with instant grammar feedback.</p>
          <span class="lp-door-cta">Start →</span>
        </a>
        <a class="lp-door" href="/Reading_Comprehension" target="_self">
          <div class="lp-door-ic" style="background:#f0fdf4;">📖</div>
          <h3>Reading Comprehension</h3>
          <p>Timed passages modeled on the official exam.</p>
          <span class="lp-door-cta">Start →</span>
        </a>
        <a class="lp-door" href="http://localhost:5002" target="_blank">
          <div class="lp-door-ic" style="background:#fefce8;">📚</div>
          <h3>Flashcards</h3>
          <p>Build vocabulary with spaced repetition.</p>
          <span class="lp-door-cta">Open →</span>
        </a>
      </div>
```

- [ ] **Step 4: Remove the start button row**

At the end of `render_welcome()`, delete the now-redundant button block (the doors replace it):

```python
    st.markdown("")

    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("Start a writing exam / Commencer un examen d'écriture", type="primary", use_container_width=True):
            go_to("setup")
            st.rerun()
    with col2:
        st.link_button(
            "📚 Flashcard Study",
            "http://localhost:5002",
            help="Open the Lexique vocabulary flashcard app",
            use_container_width=True,
        )
```

Leave the rest of `render_welcome()` (the `_use_twothirds_layout()` call and the `st.html` content wrapper) intact.

- [ ] **Step 5: Manual smoke check**

Run: `streamlit run app.py` and open http://localhost:8501
Expected: home shows the top nav, the single-column hero, and three door-cards (no mock-UI card, no "Core Features" grid). Clicking "Writing Expression" enters the setup stage; "Reading Comprehension" opens the Reading page; "Flashcards" opens :5002 in a new tab. Stop the server (Ctrl+C) when done.

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "feat: unified home with hero + three feature doors"
```

---

### Task 5: Flashcard top nav (React)

**Files:**
- Create: `flashcard/src/components/TopNav.jsx`
- Modify: `flashcard/src/App.jsx` (render `<TopNav>` at top of `<main>`)
- Modify: `flashcard/src/index.css` (add `.sle-topnav` styles)
- Rebuild: `flashcard/static/dist/` (committed Vite output)

No JS unit test (the project has no JS test setup); verified manually in Task 6.

- [ ] **Step 1: Create the TopNav component**

Create `flashcard/src/components/TopNav.jsx`:

```jsx
const STREAMLIT_URL = 'http://localhost:8501';

export default function TopNav({ active }) {
  const link = (name) => 'sle-nav-link' + (active === name ? ' active' : '');
  return (
    <nav className="sle-topnav">
      <a className="sle-brand" href={STREAMLIT_URL}>🇨🇦 SLE Prep</a>
      <a className={link('writing')} href={`${STREAMLIT_URL}/?goto=writing`}>Writing</a>
      <a className={link('reading')} href={`${STREAMLIT_URL}/Reading_Comprehension`}>Reading</a>
      <a className={link('flashcards')} href="#/">Flashcards</a>
    </nav>
  );
}
```

- [ ] **Step 2: Render TopNav in App.jsx**

In `flashcard/src/App.jsx`, add the import at the top with the other imports:

```jsx
import TopNav from './components/TopNav.jsx';
```

Then render it as the first child of `<main className="main">`, immediately before `<Routes>`:

```jsx
      <main className="main">
        <TopNav active="flashcards" />
        <Routes>
```

- [ ] **Step 3: Add the nav CSS**

In `flashcard/src/index.css`, append:

```css
/* ── Shared cross-app top nav ───────────────────────────────────────────── */
.sle-topnav {
  display: flex; align-items: center; gap: 22px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 12px; padding: 12px 20px; margin-bottom: 20px;
  box-shadow: 0 2px 8px rgba(37,99,235,0.06);
}
.sle-topnav .sle-brand {
  font-weight: 800; font-size: 15px; color: var(--ink);
  text-decoration: none; margin-right: auto; letter-spacing: -0.02em;
}
.sle-topnav .sle-nav-link {
  font-weight: 600; font-size: 14px; color: var(--ink-muted);
  text-decoration: none; padding: 6px 2px;
  border-bottom: 2px solid transparent; transition: color .15s;
}
.sle-topnav .sle-nav-link:hover { color: var(--primary); }
.sle-topnav .sle-nav-link.active {
  color: var(--primary); border-bottom-color: var(--primary);
}
```

- [ ] **Step 4: Install deps if needed and build**

Run:
```bash
cd flashcard && npm install && npm run build
```
Expected: Vite writes updated assets to `flashcard/static/dist/` with no errors.

- [ ] **Step 5: Manual smoke check**

Run: `python flashcard/app.py` and open http://localhost:5002
Expected: the top nav bar appears above the flashcard content with "Flashcards" highlighted; "Writing" and "Reading" links point back to :8501. The existing left sidebar (Dashboard/Progress/Inbox) is unchanged. Stop the server when done.

- [ ] **Step 6: Commit**

```bash
git add flashcard/src/components/TopNav.jsx flashcard/src/App.jsx flashcard/src/index.css flashcard/static/dist
git commit -m "feat: add shared top nav to flashcard app"
```

---

### Task 6: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run the whole test suite**

Run: `python -m pytest tests/ -q`
Expected: all tests pass (existing suite + `test_top_nav.py` + `test_app_nav.py`).

- [ ] **Step 2: End-to-end navigation check**

Launch both servers in separate terminals:
```bash
streamlit run app.py
python flashcard/app.py
```
Verify each link routes correctly in all directions:
- Home (:8501) → top nav present (active "home"); 3 doors visible; no mock-UI/feature grid.
- Home "Writing" door / nav "Writing" → writing setup stage (active "writing").
- Nav "Reading" → Reading page (active "reading"), timer still works on a started exam.
- Nav / door "Flashcards" → :5002 with top nav (active "flashcards").
- From :5002, "Writing" → :8501 writing setup; "Reading" → :8501 Reading page.
- Confirm colors, fonts, spacing read as one product across all three.

- [ ] **Step 3: Final commit (if any verification fixups were needed)**

```bash
git add -A
git commit -m "chore: verification fixups for unified web design"
```
(Skip if Step 1–2 needed no changes.)

---

## Self-Review

**Spec coverage:**
- Shared top nav bar (Streamlit + React) → Tasks 1, 3, 5. ✓
- `?goto=writing` Writing link → Task 2. ✓
- Hide Streamlit sidebar page nav → Task 1 (CSS in `_render_top_nav`). ✓
- Unified home (hero + 3 doors, marketing removed) → Task 4. ✓
- Refined tokens / door-card component → Task 4 (door CSS); nav reuses existing tokens. ✓
- Flashcard restyle → narrowed to nav-only (tokens already match — noted in header). Task 5. ✓
- Vite rebuild of committed dist → Task 5 Step 4. ✓
- Tests still pass (incl. timer) → Tasks 3 & 6. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code. ✓

**Type/name consistency:** `_render_top_nav(active)` and `FLASHCARD_URL` consistent across Tasks 1/3; `_resolve_initial_stage(current_stage, query_params)` consistent across Task 2; `<TopNav active=...>` and `.sle-topnav` / `.sle-nav-link` class names consistent across Tasks 1 (Streamlit) and 5 (React). ✓
