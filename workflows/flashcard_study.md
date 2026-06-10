# Flashcard Study App — Workflow SOP

## Objective

Provide a vocabulary flashcard system for SLE preparation: organize French words into decks, study them in three modes with voice pronunciation, track mastery per card, and grow the collection via AI generation and a cross-app vocab inbox fed by the Writing and Reading Comprehension simulators.

## Required Inputs

- **None for core study** — decks, cards, study modes, mastery tracking, and voice pronunciation all work offline with no API key
- An API key (`FLASHCARD_API_KEY` or fallback `DEEPSEEK_API_KEY` in `.env`) is required **only** for the AI features: generate cards from a topic, extract cards from pasted text, and enrich inbox words into full cards

## Tools Used

| Tool | Purpose |
|---|---|
| `flashcard/app.py` | Flask 3 server (port 5002): all REST routes, SQLite schema, AI card generation, SPA serving |
| `tools/flashcard_db.py` | Shared inbox helper — `add_to_inbox()` lets the exam apps write words to `flashcard/flashcard.db` without the flashcard server running |
| `tools/model_config.py` | `FLASHCARD_*` env vars resolve the AI model settings (falls back to `DEEPSEEK_API_KEY` + `deepseek-v4-pro`) |
| `flashcard/src/lib/speech.js` | Web Speech API wrapper for voice pronunciation — browser-side, no API call |
| `flashcard/context/lexique-backup-*.json` | Seed vocabulary loaded into the database on first run |

## How to Run

```bash
pip install -r requirements.txt
python flashcard/app.py
```

Then open `http://localhost:5002`. The React SPA is served from the committed Vite build (`flashcard/static/dist/`) — no Node.js needed in production.

**Frontend development only:** `cd flashcard && npm install && npm run dev` (Vite dev server proxying the Flask API). After changing anything under `flashcard/src/`, run `npm run build` and commit the updated `flashcard/static/dist/`.

**Database:** `flashcard/flashcard.db` (SQLite, gitignored) is auto-created on first run and seeded from the bundled lexique JSON (tables: `decks`, `cards`, `sessions`, `inbox`, `seed_meta`). Deleting it resets the app to seed state.

## Workflow Steps

1. **Dashboard** (`#/`) — overview stats (total cards, mastered, decks, overall mastery %) and the deck grid. Create decks with "+ New deck"; delete with ✕. The shared top nav links back to the Writing/Reading apps on `:8501`.
2. **Deck view** (`#/deck/<id>`) — card table with search, plus a 🔊 speaker button on every row that pronounces the French word. Three ways to add cards:
   - **+ Add card** — manual entry (front, type, English, 中文, example)
   - **✦ From topic** — AI generates N cards for a topic (e.g. "government procurement"); preview before committing
   - **✦ From text** — AI extracts vocabulary from a pasted French passage; preview before committing
3. **Study session** (`#/deck/<id>/study`) — pick a mode:
   - **Flashcard flip** — reveal translation, self-grade Hard / Got it
   - **Multiple choice** — pick the English translation from 4 options (needs ≥ 4 cards in the deck)
   - **Type the answer** — type the English translation; accent-insensitive matching against `/`- or `,`-separated variants (needs ≥ 2 cards)
   Every mode shows a 🔊 button next to the French word. The topbar has an **auto-play toggle** (default off, persisted in localStorage `flashcard-autoplay`) that pronounces each new card automatically.
4. **Mastery tracking** — each answer updates the card: correct = mastery +1, wrong = −1, clamped to 0–3 (`POST /api/cards/<id>/mastery`). Labels: 0 = New, 1–2 = Learning, 3 = Mastered. Session results (score %, correct/incorrect counts) are saved on completion.
5. **Progress** (`#/progress`) — mastery distribution bars and per-session history.
6. **Vocab Inbox** (`#/inbox`) — the cross-app loop:
   - During Writing or Reading exams, the Vocab Note sidebar saves unknown words to the inbox via `tools/flashcard_db.py:add_to_inbox()` (works even when the flashcard server is down)
   - In the inbox, select pending words → **AI generate** enriches them into full cards (type, translations, example) → review → **commit** to a chosen deck, or dismiss words you don't want

## Voice Pronunciation (TTS)

- Browser Web Speech API via `flashcard/src/lib/speech.js` — zero cost, no backend, no audio storage
- Voice preference: `fr-CA` > `fr-FR` > any `fr-*` > browser default with `lang='fr-FR'`
- `SpeakerButton` renders nothing in browsers without `speechSynthesis`; the auto-play toggle hides too
- Rapid clicks and card advances cancel in-flight speech (no overlap); speech stops on session end and unmount
- Only the French word (`front`) is spoken — not examples or translations

## AI Generation Prompt Design

All three AI flows (`/api/ai/from-topic`, `/api/ai/from-text`, `/api/inbox/generate`) share `_call_ai()`: JSON output, French workplace vocabulary register, each card with `front`, `type`, `en`, `zh`, `example`. Generated cards are always shown as a preview table first — nothing is written until the user commits.

## API Call Summary

| Action | Calls |
|---|---|
| Study session (any mode, any length) | 0 |
| Voice pronunciation | 0 (browser TTS) |
| AI from topic / from text / inbox generate | 1 each |
| Commit previewed cards | 0 |

## Output Files

| File | Location | Persistence |
|---|---|---|
| Flashcard database | `flashcard/flashcard.db` | Persistent (SQLite, gitignored, auto-created + seeded on first run) |

## Known Limitations

- AI-generated cards can contain errors — the preview step is the only quality gate; there is no automated review like the exam pipeline has
- Voice quality depends on the French voices installed in the user's browser/OS (Edge/Chrome on Windows 11 ship good ones); there is no user-facing voice picker
- The type-in mode matches only the English field, accent-insensitively — synonyms not listed on the card are marked wrong
- Cross-app nav hardcodes ports (`:5002` ↔ `:8501`) — fine for local dev, breaks on non-default ports
- Single-user, local-only: no auth, no sync; the SQLite file is the entire state

## Future Improvements

- Spaced-repetition scheduling (currently any session shuffles the whole deck)
- Speaking practice (STT pronunciation scoring) — explicitly out of scope of the current TTS feature
- Audio for example sentences
- Deck import/export (CSV/Anki)
