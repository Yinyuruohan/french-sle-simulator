import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getDecks, createDeck, deleteDeck } from '../api.js';
import Modal from '../components/Modal.jsx';
import { useToast } from '../components/Toast.jsx';

const COLORS = [
  { value: '1', label: 'Sage green' }, { value: '2', label: 'Amber' },
  { value: '3', label: 'Crimson' }, { value: '4', label: 'Ocean blue' },
  { value: '5', label: 'Plum' }, { value: '6', label: 'Teal' },
];

export default function Dashboard() {
  const [decks, setDecks] = useState([]);
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState({ name: '', src_lang: 'French', tgt_lang: 'English, 中文', color: '1' });
  const navigate = useNavigate();
  const { show, Toast } = useToast();

  const load = () => getDecks().then(setDecks).catch(() => {});
  useEffect(() => { load(); }, []);

  const totalCards = decks.reduce((s, d) => s + (d.card_count || 0), 0);
  const totalMastered = decks.reduce((s, d) => s + (d.mastered_count || 0), 0);

  async function handleCreate() {
    if (!form.name.trim()) return;
    await createDeck(form);
    setModal(false);
    setForm({ name: '', src_lang: 'French', tgt_lang: 'English, 中文', color: '1' });
    load();
    show('Deck created');
  }

  async function handleDelete(e, id) {
    e.stopPropagation();
    if (!confirm('Delete this deck and all its cards?')) return;
    await deleteDeck(id);
    load();
    show('Deck deleted');
  }

  return (
    <>
      <div className="topbar">
        <span className="topbar-title">Dashboard</span>
        <div className="topbar-actions">
          <button className="btn btn-primary" onClick={() => setModal(true)}>+ New deck</button>
        </div>
      </div>

      <div className="view">
        <div className="stats-row">
          <div className="stat-card">
            <div className="stat-label">Total cards</div>
            <div className="stat-value">{totalCards}</div>
            <div className="stat-sub">across all decks</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Mastered</div>
            <div className="stat-value">{totalMastered}</div>
            <div className="stat-sub">cards learned</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Decks</div>
            <div className="stat-value">{decks.length}</div>
            <div className="stat-sub">total decks</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Progress</div>
            <div className="stat-value">
              {totalCards ? Math.round(totalMastered / totalCards * 100) + '%' : '—'}
            </div>
            <div className="stat-sub">overall mastery</div>
          </div>
        </div>

        <div className="section-title">Your decks</div>
        <div className="deck-grid">
          {decks.map(d => (
            <div key={d.id} className="deck-card" onClick={() => navigate(`/deck/${d.id}`)}>
              <div className={`deck-accent accent-${d.color}`} />
              <div className="deck-card-name">{d.name}</div>
              <div className="deck-card-meta">{d.src_lang} → {d.tgt_lang}</div>
              <div className="deck-card-stats">
                <span>{d.card_count} cards</span>
                <span>{d.mastered_count} mastered</span>
                <button className="icon-btn" onClick={e => handleDelete(e, d.id)}>✕</button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <Modal open={modal} title="New deck" onClose={() => setModal(false)}>
        <div className="form-row">
          <label className="form-label">Deck name</label>
          <input className="form-input" value={form.name} onChange={e => setForm({...form, name: e.target.value})} placeholder="e.g. French Business Vocabulary" />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 14 }}>
          <div className="form-row" style={{ marginBottom: 0 }}>
            <label className="form-label">Source language</label>
            <input className="form-input" value={form.src_lang} onChange={e => setForm({...form, src_lang: e.target.value})} />
          </div>
          <div className="form-row" style={{ marginBottom: 0 }}>
            <label className="form-label">Target language(s)</label>
            <input className="form-input" value={form.tgt_lang} onChange={e => setForm({...form, tgt_lang: e.target.value})} />
          </div>
        </div>
        <div className="form-row">
          <label className="form-label">Color</label>
          <select className="form-select" value={form.color} onChange={e => setForm({...form, color: e.target.value})}>
            {COLORS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
          </select>
        </div>
        <div className="modal-footer">
          <button className="btn" onClick={() => setModal(false)}>Cancel</button>
          <button className="btn btn-primary" onClick={handleCreate}>Save deck</button>
        </div>
      </Modal>

      <Toast />
    </>
  );
}
