import { Routes, Route, NavLink } from 'react-router-dom';
import { useState, useEffect, useCallback } from 'react';
import { getInbox } from './api.js';
import Dashboard from './views/Dashboard.jsx';
import DeckView from './views/DeckView.jsx';
import StudySession from './views/StudySession.jsx';
import Inbox from './views/Inbox.jsx';
import Progress from './views/Progress.jsx';

export default function App() {
  const [inboxCount, setInboxCount] = useState(0);

  const refreshInbox = useCallback(() => {
    getInbox().then(rows => setInboxCount(rows.length)).catch(() => {});
  }, []);

  useEffect(() => {
    refreshInbox();
    const id = setInterval(refreshInbox, 30000);
    return () => clearInterval(id);
  }, [refreshInbox]);

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-text">Lexique</div>
          <div className="logo-sub">Vocabulary Flashcards</div>
        </div>
        <nav className="sidebar-nav">
          <div className="nav-section-label">Overview</div>
          <NavLink to="/" end className={({isActive}) => 'nav-btn' + (isActive ? ' active' : '')}>
            <span className="nav-icon">⌂</span> Dashboard
          </NavLink>
          <NavLink to="/progress" className={({isActive}) => 'nav-btn' + (isActive ? ' active' : '')}>
            <span className="nav-icon">◎</span> Progress
          </NavLink>
          <NavLink to="/inbox" className={({isActive}) => 'nav-btn' + (isActive ? ' active' : '')}>
            <span className="nav-icon">✉</span> Vocab Inbox
            {inboxCount > 0 && <span className="inbox-badge">{inboxCount}</span>}
          </NavLink>
        </nav>
      </aside>

      <main className="main">
        <Routes>
          <Route path="/" element={<Dashboard onInboxChange={refreshInbox} />} />
          <Route path="/deck/:id" element={<DeckView />} />
          <Route path="/deck/:id/study" element={<StudySession />} />
          <Route path="/inbox" element={<Inbox onInboxChange={refreshInbox} />} />
          <Route path="/progress" element={<Progress />} />
        </Routes>
      </main>
    </div>
  );
}
