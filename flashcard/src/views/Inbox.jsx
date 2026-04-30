import { useState, useEffect } from 'react';
import { getInbox, dismissInbox, generateFromInbox, commitInbox, getDecks } from '../api.js';
import { useToast } from '../components/Toast.jsx';

export default function Inbox({ onInboxChange }) {
  const [rows, setRows] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [decks, setDecks] = useState([]);
  const [preview, setPreview] = useState(null);
  const [targetDeck, setTargetDeck] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { show, Toast } = useToast();

  const load = () => {
    getInbox().then(r => { setRows(r); onInboxChange?.(); }).catch(() => {});
    getDecks().then(d => { setDecks(d); if (d.length) setTargetDeck(d[0].id); }).catch(() => {});
  };

  useEffect(() => { load(); }, []);

  function toggleAll(checked) {
    setSelected(checked ? new Set(rows.map(r => r.id)) : new Set());
  }

  function toggle(id) {
    setSelected(s => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  }

  async function handleDismiss() {
    const ids = [...selected];
    if (!ids.length) return;
    await dismissInbox(ids);
    setSelected(new Set());
    load();
    show(`${ids.length} word(s) dismissed`);
  }

  async function handleGenerate() {
    const ids = [...selected];
    if (!ids.length) return;
    setLoading(true);
    setError('');
    setPreview(null);
    try {
      const cards = await generateFromInbox(ids);
      setPreview(cards);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleCommit() {
    const ids = [...selected];
    if (!preview?.length || !targetDeck) return;
    await commitInbox(preview, targetDeck, ids);
    setPreview(null);
    setSelected(new Set());
    load();
    show(`${preview.length} card(s) added to deck`);
  }

  return (
    <>
      <div className="topbar">
        <span className="topbar-title">Vocab Inbox</span>
        <div className="topbar-actions">
          {selected.size > 0 && !preview && (
            <>
              <button className="btn btn-danger" onClick={handleDismiss}>Dismiss ({selected.size})</button>
              <button className="btn btn-primary" onClick={handleGenerate} disabled={loading}>
                {loading ? 'Generating…' : `Generate cards (${selected.size})`}
              </button>
            </>
          )}
        </div>
      </div>

      <div className="view">
        {rows.length === 0 && !loading && (
          <div style={{ textAlign: 'center', padding: 60, color: 'var(--ink-muted)' }}>
            <div style={{ fontSize: 32, marginBottom: 12 }}>✉</div>
            <div>Your inbox is empty. Words you save during the SLE exam will appear here.</div>
          </div>
        )}

        {rows.length > 0 && !preview && (
          <div className="vocab-table">
            <table>
              <thead>
                <tr>
                  <th style={{ width: 36 }}>
                    <input type="checkbox" checked={selected.size === rows.length && rows.length > 0}
                      onChange={e => toggleAll(e.target.checked)} style={{ accentColor: 'var(--sage)' }} />
                  </th>
                  <th>Word / Phrase</th>
                  <th>Source</th>
                  <th>Added</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(r => (
                  <tr key={r.id}>
                    <td>
                      <input type="checkbox" checked={selected.has(r.id)}
                        onChange={() => toggle(r.id)} style={{ accentColor: 'var(--sage)' }} />
                    </td>
                    <td className="td-fr">{r.word}</td>
                    <td style={{ color: 'var(--ink-muted)', fontSize: 12 }}>{r.source}</td>
                    <td style={{ color: 'var(--ink-muted)', fontSize: 12 }}>{r.added_at.slice(0, 10)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {loading && (
          <div style={{ textAlign: 'center', padding: 48 }}>
            <div className="spinner" />
            <p style={{ fontSize: 13, color: 'var(--ink-muted)', marginTop: 14 }}>Generating flashcards with AI…</p>
          </div>
        )}

        {error && (
          <div style={{ background: 'var(--red-light)', border: '1px solid #E8B0B0', borderRadius: 'var(--radius-sm)', padding: 14, fontSize: 13, color: 'var(--red)', marginTop: 16 }}>
            {error}
          </div>
        )}

        {preview && (
          <>
            <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 13, color: 'var(--ink-muted)' }}>Preview — {preview.length} card(s) generated</span>
              <button className="btn" style={{ fontSize: 12 }} onClick={() => setPreview(null)}>← Back</button>
            </div>
            <div className="vocab-table" style={{ marginBottom: 20 }}>
              <table>
                <thead>
                  <tr>
                    <th>Word</th><th>Type</th><th>English</th><th>中文</th><th>Example</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.map((c, i) => (
                    <tr key={i}>
                      <td className="td-fr">{c.front}</td>
                      <td className="td-type">{c.type}</td>
                      <td>{c.en}</td>
                      <td>{c.zh}</td>
                      <td style={{ fontSize: 12, color: 'var(--ink-muted)', fontStyle: 'italic' }}>{c.example}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
              <select className="form-select" style={{ maxWidth: 240 }} value={targetDeck} onChange={e => setTargetDeck(e.target.value)}>
                {decks.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
              <button className="btn btn-primary" onClick={handleCommit}>Add to deck</button>
            </div>
          </>
        )}
      </div>
      <Toast />
    </>
  );
}
