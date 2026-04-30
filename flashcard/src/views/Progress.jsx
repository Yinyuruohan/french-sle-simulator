import { useState, useEffect } from 'react';
import { getDecks, getSessions } from '../api.js';

export default function Progress() {
  const [decks, setDecks] = useState([]);
  const [sessions, setSessions] = useState([]);

  useEffect(() => {
    getDecks().then(setDecks).catch(() => {});
    getSessions().then(setSessions).catch(() => {});
  }, []);

  return (
    <>
      <div className="topbar"><span className="topbar-title">Progress</span></div>
      <div className="view">
        <div className="progress-grid">
          <div className="progress-card">
            <div className="progress-card-title">Mastery by deck</div>
            {decks.map(d => {
              const pct = d.card_count ? Math.round(d.mastered_count / d.card_count * 100) : 0;
              return (
                <div key={d.id} className="bar-row">
                  <span className="bar-label" title={d.name}>{d.name}</span>
                  <div className="bar-track">
                    <div className="bar-fill" style={{ width: pct + '%' }} />
                  </div>
                  <span className="bar-val">{pct}%</span>
                </div>
              );
            })}
            {decks.length === 0 && <p style={{ color: 'var(--ink-muted)', fontSize: 13 }}>No decks yet.</p>}
          </div>

          <div className="progress-card">
            <div className="progress-card-title">Recent sessions</div>
            {sessions.slice(0, 10).map(s => (
              <div key={s.id} className="history-item">
                <span className="history-date">{s.studied_at.slice(0, 10)}</span>
                <span style={{ color: 'var(--ink-muted)', fontSize: 13 }}>{s.cards_studied} cards</span>
                <span className="history-score">{s.score_pct}%</span>
              </div>
            ))}
            {sessions.length === 0 && <p style={{ color: 'var(--ink-muted)', fontSize: 13 }}>No sessions yet.</p>}
          </div>
        </div>
      </div>
    </>
  );
}
