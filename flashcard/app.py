import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_file, send_from_directory

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


# ── Static serving ────────────────────────────────────────────────────────────

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_spa(path):
    target = STATIC_DIR / path
    if path and target.is_file():
        return send_from_directory(STATIC_DIR, path)
    return send_file(STATIC_DIR / 'index.html')


if __name__ == '__main__':
    init_db()
    app.run(port=5002, debug=True)
