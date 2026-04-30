import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getDecks, getCards, addCard, updateCard, deleteCard, aiFromTopic, aiFromText, aiCommit } from '../api.js';
import Modal from '../components/Modal.jsx';
import { useToast } from '../components/Toast.jsx';

const EMPTY_FORM = { front: '', type: '', en: '', zh: '', example: '' };

export default function DeckView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [deck, setDeck] = useState(null);
  const [cards, setCards] = useState([]);
  const [tab, setTab] = useState('manage');
  const [search, setSearch] = useState('');
  const [modal, setModal] = useState(false);
  const [editId, setEditId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [aiModal, setAiModal] = useState(null);
  const [aiForm, setAiForm] = useState({ topic: '', count: 10, text: '' });
  const [aiPreview, setAiPreview] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState('');
  const { show, Toast } = useToast();

  const loadCards = () => getCards(id).then(setCards).catch(() => {});
  useEffect(() => {
    getDecks().then(ds => setDeck(ds.find(d => d.id === id))).catch(() => {});
    loadCards();
  }, [id]);

  const filtered = cards.filter(c =>
    !search || c.front.toLowerCase().includes(search.toLowerCase()) ||
    (c.en || '').toLowerCase().includes(search.toLowerCase())
  );

  function openAdd() { setEditId(null); setForm(EMPTY_FORM); setModal(true); }
  function openEdit(card) {
    setEditId(card.id);
    setForm({ front: card.front, type: card.type, en: card.en, zh: card.zh, example: card.example });
    setModal(true);
  }

  async function handleSave() {
    if (!form.front.trim()) return;
    if (editId) {
      await updateCard(editId, form);
      show('Card updated');
    } else {
      await addCard(id, form);
      show('Card added');
    }
    setModal(false);
    loadCards();
  }

  async function handleDelete(cid) {
    if (!confirm('Delete this card?')) return;
    await deleteCard(cid);
    loadCards();
    show('Card deleted');
  }

  function masteryLabel(m) {
    if (m === 0) return <span className="mastery-badge mastery-new">New</span>;
    if (m < 3) return <span className="mastery-badge mastery-learning">Learning</span>;
    return <span className="mastery-badge mastery-mastered">Mastered</span>;
  }

  async function handleAiGenerate() {
    setAiLoading(true);
    setAiError('');
    setAiPreview(null);
    try {
      const generated = aiModal === 'topic'
        ? await aiFromTopic(aiForm.topic, aiForm.count)
        : await aiFromText(aiForm.text);
      setAiPreview(generated);
    } catch (e) {
      setAiError(e.message);
    } finally {
      setAiLoading(false);
    }
  }

  async function handleAiCommit() {
    if (!aiPreview?.length) return;
    await aiCommit(aiPreview, id);
    setAiModal(null);
    setAiPreview(null);
    setAiForm({ topic: '', count: 10, text: '' });
    loadCards();
    show(`${aiPreview.length} card(s) added`);
  }

  if (!deck) return <div className="view">Loading...</div>;

  return (
    <>
      <div className="topbar">
        <span className="topbar-title">{deck.name}</span>
        <div className="topbar-actions">
          <button className="btn" onClick={() => navigate('/')}>← Back</button>
          <button className="btn btn-primary" onClick={() => navigate(`/deck/${id}/study`)}>
            Study →
          </button>
        </div>
      </div>

      <div className="view">
        <div className="tabs">
          <button className={`tab ${tab === 'manage' ? 'active' : ''}`} onClick={() => setTab('manage')}>Manage cards</button>
          <button className={`tab ${tab === 'study' ? 'active' : ''}`} onClick={() => navigate(`/deck/${id}/study`)}>Study</button>
        </div>

        <div className="toolbar">
          <input className="search-input" placeholder="Search cards..." value={search} onChange={e => setSearch(e.target.value)} />
          <button className="btn btn-primary" onClick={openAdd}>+ Add card</button>
          <button className="btn" onClick={() => { setAiModal('topic'); setAiPreview(null); setAiError(''); }}>
            ✦ From topic
          </button>
          <button className="btn" onClick={() => { setAiModal('text'); setAiPreview(null); setAiError(''); }}>
            ✦ From text
          </button>
        </div>

        <div className="vocab-table">
          <table>
            <thead>
              <tr>
                <th>Word / Phrase</th>
                <th>Type</th>
                <th>English</th>
                <th>中文</th>
                <th>Mastery</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(card => (
                <tr key={card.id}>
                  <td className="td-fr">{card.front}</td>
                  <td className="td-type">{card.type}</td>
                  <td>{card.en}</td>
                  <td>{card.zh}</td>
                  <td>{masteryLabel(card.mastery)}</td>
                  <td>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button className="icon-btn" onClick={() => openEdit(card)}>✎</button>
                      <button className="icon-btn btn-danger" onClick={() => handleDelete(card.id)}>✕</button>
                    </div>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--ink-muted)', padding: 32 }}>No cards yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <Modal open={modal} title={editId ? 'Edit card' : 'Add card'} onClose={() => setModal(false)}>
        <div className="form-row">
          <label className="form-label">Source word / phrase</label>
          <input className="form-input" value={form.front} onChange={e => setForm({...form, front: e.target.value})} placeholder="e.g. atelier" />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 14 }}>
          <div className="form-row" style={{ marginBottom: 0 }}>
            <label className="form-label">Word type</label>
            <input className="form-input" value={form.type} onChange={e => setForm({...form, type: e.target.value})} placeholder="e.g. nom masc." />
          </div>
          <div className="form-row" style={{ marginBottom: 0 }}>
            <label className="form-label">English</label>
            <input className="form-input" value={form.en} onChange={e => setForm({...form, en: e.target.value})} placeholder="e.g. workshop" />
          </div>
        </div>
        <div className="form-row">
          <label className="form-label">中文 (optional)</label>
          <input className="form-input" value={form.zh} onChange={e => setForm({...form, zh: e.target.value})} placeholder="e.g. 工作坊" />
        </div>
        <div className="form-row">
          <label className="form-label">Example sentence</label>
          <textarea className="form-textarea" value={form.example} onChange={e => setForm({...form, example: e.target.value})} placeholder="e.g. Nous organiserons un atelier..." />
        </div>
        <div className="modal-footer">
          <button className="btn" onClick={() => setModal(false)}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave}>Save card</button>
        </div>
      </Modal>

      <Modal open={!!aiModal} title={aiModal === 'topic' ? 'Generate from topic' : 'Generate from text'} onClose={() => setAiModal(null)} wide>
        {!aiPreview && !aiLoading && (
          <>
            {aiModal === 'topic' && (
              <>
                <div className="form-row">
                  <label className="form-label">Topic</label>
                  <input className="form-input" value={aiForm.topic} onChange={e => setAiForm({...aiForm, topic: e.target.value})} placeholder="e.g. government procurement, HR terminology" />
                </div>
                <div className="form-row">
                  <label className="form-label">Number of cards</label>
                  <input className="form-input" type="number" min={1} max={20} value={aiForm.count} onChange={e => setAiForm({...aiForm, count: +e.target.value})} style={{ maxWidth: 100 }} />
                </div>
              </>
            )}
            {aiModal === 'text' && (
              <div className="form-row">
                <label className="form-label">Paste text to extract vocabulary from</label>
                <textarea className="form-textarea" style={{ minHeight: 160 }} value={aiForm.text} onChange={e => setAiForm({...aiForm, text: e.target.value})} placeholder="Paste a French passage..." />
              </div>
            )}
            {aiError && <div style={{ background: 'var(--red-light)', color: 'var(--red)', padding: '10px 14px', borderRadius: 'var(--radius-sm)', fontSize: 13, marginBottom: 14 }}>{aiError}</div>}
            <div className="modal-footer">
              <button className="btn" onClick={() => setAiModal(null)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleAiGenerate}>Generate preview →</button>
            </div>
          </>
        )}
        {aiLoading && (
          <div style={{ textAlign: 'center', padding: 48 }}>
            <div className="spinner" />
            <p style={{ fontSize: 13, color: 'var(--ink-muted)', marginTop: 14 }}>Generating with AI...</p>
          </div>
        )}
        {aiPreview && (
          <>
            <div style={{ maxHeight: 320, overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', marginBottom: 16 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead style={{ position: 'sticky', top: 0, background: 'var(--cream)' }}>
                  <tr>
                    <th style={{ padding: '10px 12px', textAlign: 'left', borderBottom: '1px solid var(--border)' }}>Word</th>
                    <th style={{ padding: '10px 12px', textAlign: 'left', borderBottom: '1px solid var(--border)' }}>EN</th>
                    <th style={{ padding: '10px 12px', textAlign: 'left', borderBottom: '1px solid var(--border)' }}>Example</th>
                  </tr>
                </thead>
                <tbody>
                  {aiPreview.map((c, i) => (
                    <tr key={i}>
                      <td style={{ padding: '9px 12px', fontFamily: 'Lora, serif', fontWeight: 600, borderBottom: '1px solid var(--border)' }}>{c.front}</td>
                      <td style={{ padding: '9px 12px', borderBottom: '1px solid var(--border)' }}>{c.en}</td>
                      <td style={{ padding: '9px 12px', color: 'var(--ink-muted)', fontStyle: 'italic', fontSize: 12, borderBottom: '1px solid var(--border)' }}>{c.example}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="modal-footer">
              <button className="btn" onClick={() => setAiPreview(null)}>← Regenerate</button>
              <button className="btn btn-primary" onClick={handleAiCommit}>Add {aiPreview.length} cards to deck</button>
            </div>
          </>
        )}
      </Modal>

      <Toast />
    </>
  );
}
