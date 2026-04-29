# tools/flashcard_db.py
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / 'flashcard' / 'flashcard.db'


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS inbox (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                word     TEXT NOT NULL,
                source   TEXT NOT NULL DEFAULT 'exam',
                added_at TEXT NOT NULL,
                status   TEXT NOT NULL DEFAULT 'pending'
            )
        """)
        conn.commit()


init_db()


def add_to_inbox(words: list, source: str = 'exam') -> None:
    now = datetime.now(timezone.utc).isoformat()
    rows = [(w.strip(), source, now) for w in words if w.strip()]
    if not rows:
        return
    with _connect() as conn:
        conn.executemany(
            "INSERT INTO inbox (word, source, added_at, status) VALUES (?, ?, ?, 'pending')",
            rows
        )
        conn.commit()


def get_pending_inbox() -> list:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, word, source, added_at FROM inbox "
            "WHERE status = 'pending' ORDER BY added_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def mark_inbox_status(ids: list, status: str) -> None:
    if not ids:
        return
    placeholders = ','.join('?' * len(ids))
    with _connect() as conn:
        conn.execute(
            f"UPDATE inbox SET status = ? WHERE id IN ({placeholders})",
            [status, *ids]
        )
        conn.commit()
