import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_file, send_from_directory
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.model_config import load_default_configs

import sqlite3

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / 'flashcard.db'
STATIC_DIR = BASE_DIR / 'static' / 'dist'
SEED_JSON = BASE_DIR / 'context' / 'lexique-backup-2026-04-07.json'

app = Flask(__name__, static_folder=None)


# ── DB ────────────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS decks (
                id         TEXT PRIMARY KEY,
                name       TEXT NOT NULL,
                src_lang   TEXT NOT NULL DEFAULT 'French',
                tgt_lang   TEXT NOT NULL DEFAULT 'English, 中文',
                color      TEXT NOT NULL DEFAULT '1',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cards (
                id         TEXT PRIMARY KEY,
                deck_id    TEXT NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
                front      TEXT NOT NULL,
                type       TEXT DEFAULT '',
                en         TEXT DEFAULT '',
                zh         TEXT DEFAULT '',
                example    TEXT DEFAULT '',
                mastery    INTEGER NOT NULL DEFAULT 0,
                seen       INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                deck_id       TEXT NOT NULL,
                cards_studied INTEGER NOT NULL,
                correct       INTEGER NOT NULL,
                incorrect     INTEGER NOT NULL,
                score_pct     REAL NOT NULL,
                studied_at    TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS inbox (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                word     TEXT NOT NULL,
                source   TEXT NOT NULL DEFAULT 'exam',
                added_at TEXT NOT NULL,
                status   TEXT NOT NULL DEFAULT 'pending'
            );
            CREATE TABLE IF NOT EXISTS seed_meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
    _seed_defaults()


def _uid():
    return uuid.uuid4().hex[:8]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _seed_defaults():
    with get_db() as conn:
        if conn.execute(
            "SELECT 1 FROM seed_meta WHERE key = 'decks_seeded'"
        ).fetchone():
            return
        if not SEED_JSON.exists():
            return
        with open(SEED_JSON, encoding='utf-8') as f:
            data = json.load(f)
        now = _now()
        for deck in data.get('decks', []):
            did = deck.get('id') or _uid()
            conn.execute(
                "INSERT OR IGNORE INTO decks (id,name,src_lang,tgt_lang,color,created_at) "
                "VALUES (?,?,?,?,?,?)",
                (did, deck['name'], deck.get('srcLang', 'French'),
                 deck.get('tgtLang', 'English, 中文'), str(deck.get('color', '1')), now)
            )
            for card in deck.get('cards', []):
                cid = card.get('id') or _uid()
                conn.execute(
                    "INSERT OR IGNORE INTO cards "
                    "(id,deck_id,front,type,en,zh,example,mastery,seen,created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (cid, did, card['front'], card.get('type', ''),
                     card.get('en', ''), card.get('zh', ''),
                     card.get('example', ''), card.get('mastery', 0),
                     card.get('seen', 0), now)
                )
        conn.execute("INSERT INTO seed_meta(key,value) VALUES('decks_seeded','1')")


# ── Deck routes ───────────────────────────────────────────────────────────────

@app.get('/api/decks')
def list_decks():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT d.id, d.name, d.src_lang, d.tgt_lang, d.color, d.created_at,
                   COUNT(c.id) as card_count,
                   SUM(CASE WHEN c.mastery >= 3 THEN 1 ELSE 0 END) as mastered_count
            FROM decks d LEFT JOIN cards c ON c.deck_id = d.id
            GROUP BY d.id ORDER BY d.created_at
        """).fetchall()
    return jsonify([dict(r) for r in rows])


@app.post('/api/decks')
def create_deck():
    body = request.get_json()
    deck = {
        'id': _uid(), 'name': body['name'],
        'src_lang': body.get('src_lang', 'French'),
        'tgt_lang': body.get('tgt_lang', 'English, 中文'),
        'color': str(body.get('color', '1')),
        'created_at': _now()
    }
    with get_db() as conn:
        conn.execute(
            "INSERT INTO decks(id,name,src_lang,tgt_lang,color,created_at) VALUES(?,?,?,?,?,?)",
            list(deck.values())
        )
    deck['card_count'] = 0
    deck['mastered_count'] = 0
    return jsonify(deck), 201


@app.put('/api/decks/<did>')
def update_deck(did):
    body = request.get_json()
    with get_db() as conn:
        conn.execute(
            "UPDATE decks SET name=?, color=? WHERE id=?",
            (body.get('name'), str(body.get('color', '1')), did)
        )
        row = conn.execute("SELECT * FROM decks WHERE id=?", (did,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(row))


@app.delete('/api/decks/<did>')
def delete_deck(did):
    with get_db() as conn:
        conn.execute("DELETE FROM decks WHERE id=?", (did,))
    return jsonify({'ok': True})


# ── Card routes ───────────────────────────────────────────────────────────────

@app.get('/api/decks/<did>/cards')
def list_cards(did):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM cards WHERE deck_id=? ORDER BY created_at", (did,)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.post('/api/decks/<did>/cards')
def add_card(did):
    b = request.get_json()
    card = {
        'id': _uid(), 'deck_id': did, 'front': b['front'],
        'type': b.get('type', ''), 'en': b.get('en', ''),
        'zh': b.get('zh', ''), 'example': b.get('example', ''),
        'mastery': 0, 'seen': 0, 'created_at': _now()
    }
    with get_db() as conn:
        conn.execute(
            "INSERT INTO cards(id,deck_id,front,type,en,zh,example,mastery,seen,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            list(card.values())
        )
    return jsonify(card), 201


@app.put('/api/cards/<cid>')
def update_card(cid):
    b = request.get_json()
    with get_db() as conn:
        conn.execute(
            "UPDATE cards SET front=?,type=?,en=?,zh=?,example=? WHERE id=?",
            (b['front'], b.get('type', ''), b.get('en', ''), b.get('zh', ''), b.get('example', ''), cid)
        )
        row = conn.execute("SELECT * FROM cards WHERE id=?", (cid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(row))


@app.delete('/api/cards/<cid>')
def delete_card(cid):
    with get_db() as conn:
        conn.execute("DELETE FROM cards WHERE id=?", (cid,))
    return jsonify({'ok': True})


@app.post('/api/cards/<cid>/mastery')
def update_mastery(cid):
    correct = request.get_json().get('correct', False)
    with get_db() as conn:
        row = conn.execute("SELECT mastery, seen FROM cards WHERE id=?", (cid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        new_mastery = min(3, row['mastery'] + 1) if correct else max(0, row['mastery'] - 1)
        conn.execute(
            "UPDATE cards SET mastery=?, seen=seen+1 WHERE id=?",
            (new_mastery, cid)
        )
        row = conn.execute("SELECT * FROM cards WHERE id=?", (cid,)).fetchone()
    return jsonify(dict(row))


# ── Session routes ────────────────────────────────────────────────────────────

@app.post('/api/sessions')
def save_session():
    b = request.get_json()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO sessions(deck_id,cards_studied,correct,incorrect,score_pct,studied_at) "
            "VALUES(?,?,?,?,?,?)",
            (b['deck_id'], b['cards_studied'], b['correct'],
             b['incorrect'], b['score_pct'], _now())
        )
        sid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        row = conn.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    return jsonify(dict(row)), 201


@app.get('/api/sessions')
def list_sessions():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY studied_at DESC LIMIT 30"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# ── Inbox routes ──────────────────────────────────────────────────────────────

@app.get('/api/inbox')
def list_inbox():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id,word,source,added_at FROM inbox "
            "WHERE status='pending' ORDER BY added_at DESC"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.post('/api/inbox/dismiss')
def dismiss_inbox():
    ids = request.get_json().get('ids', [])
    if ids:
        ph = ','.join('?' * len(ids))
        with get_db() as conn:
            conn.execute(f"UPDATE inbox SET status='dismissed' WHERE id IN ({ph})", ids)
    return jsonify({'ok': True})


# ── AI helper ─────────────────────────────────────────────────────────────────


def _call_ai(prompt: str) -> list:
    cfg = load_default_configs()['flashcard']
    if not cfg.api_key:
        raise ValueError("No API key configured for flashcard AI — set FLASHCARD_API_KEY or DEEPSEEK_API_KEY in .env")
    client_ai = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
    resp = client_ai.chat.completions.create(
        model=cfg.model,
        messages=[
            {'role': 'system', 'content': (
                'You generate French vocabulary flashcards. '
                'Always respond with a JSON array of objects with keys: '
                'front, type, en, zh, example. No extra text.'
            )},
            {'role': 'user', 'content': prompt}
        ],
        temperature=0.7,
        max_tokens=4096,
    )
    text = resp.choices[0].message.content
    text = re.sub(r'^```[a-z]*\n?', '', text.strip())
    text = re.sub(r'\n?```$', '', text.strip())
    return json.loads(text)


def _topic_prompt(topic: str, count: int, lang: str) -> str:
    return (
        f"Generate {count} {lang} vocabulary flashcard(s) about the topic: '{topic}'. "
        f"Each card: front={lang} word/phrase, type=grammar type in French, "
        f"en=English translation(s), zh=Chinese translation(s), "
        f"example=a realistic workplace sentence using the word. "
        f"Return a JSON array only."
    )


def _text_prompt(text: str, lang: str) -> str:
    return (
        f"Extract important {lang} vocabulary from this text and create flashcards. "
        f"Each card: front=word/phrase as it appears, type=grammar type in French, "
        f"en=English translation(s), zh=Chinese translation(s), "
        f"example=a realistic workplace sentence. Return a JSON array only.\n\nText:\n{text}"
    )


def _words_prompt(words: list, lang: str) -> str:
    word_list = '\n'.join(f'- {w}' for w in words)
    return (
        f"Define each of the following specific {lang} words/phrases as vocabulary flashcards. "
        f"Create exactly one card per word, in the same order as the list. "
        f"Each card: front=the exact word/phrase from the list, type=grammar type in French, "
        f"en=English translation(s), zh=Chinese translation(s), "
        f"example=a realistic Canadian federal workplace sentence using that word. "
        f"Return a JSON array with exactly {len(words)} objects. No extra text.\n\n"
        f"Words to define:\n{word_list}"
    )


# ── AI routes ─────────────────────────────────────────────────────────────────

@app.post('/api/ai/from-topic')
def ai_from_topic():
    b = request.get_json()
    try:
        cards = _call_ai(_topic_prompt(b['topic'], b.get('count', 10), b.get('lang', 'French')))
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify(cards)


@app.post('/api/ai/from-text')
def ai_from_text():
    b = request.get_json()
    try:
        cards = _call_ai(_text_prompt(b['text'], b.get('lang', 'French')))
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify(cards)


@app.post('/api/ai/commit')
def ai_commit():
    b = request.get_json()
    deck_id = b['deck_id']
    now = _now()
    with get_db() as conn:
        for card in b.get('cards', []):
            conn.execute(
                "INSERT INTO cards(id,deck_id,front,type,en,zh,example,mastery,seen,created_at) "
                "VALUES(?,?,?,?,?,?,?,0,0,?)",
                (_uid(), deck_id, card['front'], card.get('type', ''),
                 card.get('en', ''), card.get('zh', ''), card.get('example', ''), now)
            )
    return jsonify({'ok': True, 'added': len(b.get('cards', []))})


@app.post('/api/inbox/generate')
def inbox_generate():
    ids = request.get_json().get('ids', [])
    if not ids:
        return jsonify([])
    ph = ','.join('?' * len(ids))
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT word FROM inbox WHERE id IN ({ph})", ids
        ).fetchall()
    words = [r['word'] for r in rows]
    prompt = _words_prompt(words, 'French')
    try:
        cards = _call_ai(prompt)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify(cards)


@app.post('/api/inbox/commit')
def inbox_commit():
    b = request.get_json()
    deck_id = b['deck_id']
    ids = b.get('ids', [])
    now = _now()
    with get_db() as conn:
        for card in b.get('cards', []):
            conn.execute(
                "INSERT INTO cards(id,deck_id,front,type,en,zh,example,mastery,seen,created_at) "
                "VALUES(?,?,?,?,?,?,?,0,0,?)",
                (_uid(), deck_id, card['front'], card.get('type', ''),
                 card.get('en', ''), card.get('zh', ''), card.get('example', ''), now)
            )
        if ids:
            ph = ','.join('?' * len(ids))
            conn.execute(f"UPDATE inbox SET status='added' WHERE id IN ({ph})", ids)
    return jsonify({'ok': True})


# ── Static serving ────────────────────────────────────────────────────────────

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_spa(path):
    target = STATIC_DIR / path
    if path and target.is_file():
        return send_from_directory(STATIC_DIR, path)
    return send_file(STATIC_DIR / 'index.html')


if __name__ == '__main__':
    import os as _os
    init_db()
    app.run(port=5002, debug=_os.environ.get("FLASK_DEBUG", "0") == "1")
