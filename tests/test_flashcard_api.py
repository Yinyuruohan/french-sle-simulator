# tests/test_flashcard_api.py
import json
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

@pytest.fixture
def client(tmp_path, monkeypatch):
    import flashcard.app as fa
    monkeypatch.setattr(fa, 'DB_PATH', tmp_path / 'test.db')
    monkeypatch.setattr(fa, 'SEED_JSON', Path('nonexistent.json'))
    fa.init_db()
    fa.app.config['TESTING'] = True
    with fa.app.test_client() as c:
        yield c

def test_list_decks_empty(client):
    r = client.get('/api/decks')
    assert r.status_code == 200
    assert r.get_json() == []

def test_create_deck(client):
    r = client.post('/api/decks', json={
        'name': 'Test Deck', 'src_lang': 'French',
        'tgt_lang': 'English', 'color': '1'
    })
    assert r.status_code == 201
    data = r.get_json()
    assert data['name'] == 'Test Deck'
    assert 'id' in data

def test_update_deck(client):
    r = client.post('/api/decks', json={'name': 'Old', 'src_lang': 'French', 'tgt_lang': 'EN', 'color': '1'})
    did = r.get_json()['id']
    r2 = client.put(f'/api/decks/{did}', json={'name': 'New', 'color': '2'})
    assert r2.status_code == 200
    assert r2.get_json()['name'] == 'New'

def test_delete_deck(client):
    r = client.post('/api/decks', json={'name': 'Del', 'src_lang': 'French', 'tgt_lang': 'EN', 'color': '1'})
    did = r.get_json()['id']
    assert client.delete(f'/api/decks/{did}').status_code == 200
    assert client.get('/api/decks').get_json() == []
