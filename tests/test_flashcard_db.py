# tests/test_flashcard_db.py
import pytest
import sqlite3

@pytest.fixture
def db(tmp_path, monkeypatch):
    import tools.flashcard_db as fdb
    monkeypatch.setattr(fdb, 'DB_PATH', tmp_path / 'test.db')
    fdb.init_db()
    return fdb

def test_init_creates_inbox_table(db, tmp_path):
    conn = sqlite3.connect(tmp_path / 'test.db')
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    assert 'inbox' in tables

def test_add_to_inbox_inserts_words(db):
    db.add_to_inbox(['atelier', 'allouer'], source='exam')
    rows = db.get_pending_inbox()
    assert len(rows) == 2
    words = {r['word'] for r in rows}
    assert words == {'atelier', 'allouer'}
    assert rows[0]['source'] == 'exam'

def test_add_to_inbox_skips_blank(db):
    db.add_to_inbox(['', '  ', 'atelier'])
    assert len(db.get_pending_inbox()) == 1

def test_mark_inbox_status(db):
    db.add_to_inbox(['atelier', 'allouer'])
    ids = [r['id'] for r in db.get_pending_inbox()]
    db.mark_inbox_status(ids, 'added')
    assert db.get_pending_inbox() == []

def test_mark_inbox_status_empty_list(db):
    db.add_to_inbox(['atelier'])
    db.mark_inbox_status([], 'dismissed')
    assert len(db.get_pending_inbox()) == 1
