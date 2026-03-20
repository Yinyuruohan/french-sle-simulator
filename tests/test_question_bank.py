# tests/test_question_bank.py
"""Tests for tools/question_bank.py"""
import json
import os
import sqlite3
import tempfile
import pytest


@pytest.fixture
def db_path(tmp_path):
    """Provide a temporary database path and patch DB_PATH."""
    path = str(tmp_path / "test_question_bank.db")
    import tools.question_bank as qb
    qb.DB_PATH = path
    yield path


def test_init_db_creates_table(db_path):
    """init_db creates the contexts table with expected columns."""
    from tools.question_bank import init_db
    init_db()
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("PRAGMA table_info(contexts)")
    columns = {row[1] for row in cursor.fetchall()}
    conn.close()
    expected = {"context_id", "type", "passage", "questions_json", "num_questions",
                "grammar_topics", "status", "source_session", "created_at",
                "times_served", "passage_hash", "last_incorrect"}
    assert expected == columns


def test_init_db_is_idempotent(db_path):
    """Calling init_db twice does not raise."""
    from tools.question_bank import init_db
    init_db()
    init_db()  # should not raise
