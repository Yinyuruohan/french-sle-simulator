import { useState, useEffect, useRef, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getCards, updateMastery, saveSessions } from '../api.js';

function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function normalise(s) {
  return s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
}

// ── Flip mode ─────────────────────────────────────────────────────────────────
function FlipCard({ card, onAnswer }) {
  const [flipped, setFlipped] = useState(false);
  return (
    <div className="study-card">
      <div className="study-front">{card.front}</div>
      <div className="study-type">{card.type}</div>
      {!flipped ? (
        <button className="btn btn-primary" style={{ marginTop: 20 }} onClick={() => setFlipped(true)}>
          Reveal →
        </button>
      ) : (
        <>
          <div className="study-back">
            <div className="study-translation">{card.en}</div>
            {card.zh && <div className="study-translation" style={{ color: 'var(--ink-muted)' }}>{card.zh}</div>}
            {card.example && <div className="study-example">« {card.example} »</div>}
          </div>
          <div className="study-actions">
            <button className="btn study-btn-wrong" onClick={() => onAnswer(false)}>✗ Hard</button>
            <button className="btn study-btn-correct" onClick={() => onAnswer(true)}>✓ Got it</button>
          </div>
        </>
      )}
    </div>
  );
}

// ── MCQ mode ──────────────────────────────────────────────────────────────────
function MCQCard({ card, allCards, onAnswer }) {
  const [selected, setSelected] = useState(null);
  const choices = useMemo(() => {
    const others = shuffle(allCards.filter(c => c.id !== card.id)).slice(0, 3);
    return shuffle([card, ...others]);
  }, [card.id]); // eslint-disable-line react-hooks/exhaustive-deps

  function pick(c) {
    if (selected !== null) return;
    setSelected(c.id);
    setTimeout(() => onAnswer(c.id === card.id), 1000);
  }

  return (
    <div className="study-card">
      <div style={{ fontSize: 11, fontWeight: 500, letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--ink-muted)', marginBottom: 10 }}>
        Choose the translation
      </div>
      <div className="study-front">{card.front}</div>
      <div className="study-type" style={{ marginBottom: 24 }}>{card.type}</div>
      {choices.map((c, i) => {
        let cls = 'mcq-choice';
        if (selected !== null) {
          if (c.id === card.id) cls += ' correct';
          else if (c.id === selected) cls += ' wrong';
        }
        return (
          <button key={c.id} className={cls} onClick={() => pick(c)} disabled={selected !== null}>
            <span className="choice-key">{['A','B','C','D'][i]}</span>
            <span>{c.en}</span>
          </button>
        );
      })}
    </div>
  );
}

// ── Type-in mode ──────────────────────────────────────────────────────────────
function TypeCard({ card, onAnswer }) {
  const [val, setVal] = useState('');
  const [result, setResult] = useState(null); // 'correct' | 'wrong'

  function check() {
    if (result) return;
    const correct = normalise(card.en).split(/[/,]/).some(s => normalise(s) === normalise(val));
    setResult(correct ? 'correct' : 'wrong');
    setTimeout(() => onAnswer(correct), 1200);
  }

  return (
    <div className="study-card">
      <div style={{ fontSize: 11, fontWeight: 500, letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--ink-muted)', marginBottom: 10 }}>
        Type the English translation
      </div>
      <div className="study-front">{card.front}</div>
      <div className="study-type" style={{ marginBottom: 20 }}>{card.type}</div>
      <div style={{ display: 'flex', gap: 10 }}>
        <input
          className={`type-input ${result || ''}`}
          value={val}
          onChange={e => setVal(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && check()}
          placeholder="Type translation…"
          disabled={!!result}
          autoFocus
        />
        <button className="btn btn-primary" onClick={check} disabled={!!result}>Check</button>
      </div>
      {result === 'wrong' && (
        <div style={{ marginTop: 14, padding: '10px 14px', background: 'var(--red-light)', borderRadius: 'var(--radius-sm)', fontSize: 13, color: 'var(--red)' }}>
          Correct answer: {card.en}
        </div>
      )}
    </div>
  );
}

// ── Session results ───────────────────────────────────────────────────────────
function Results({ correct, incorrect, deckId, onRestart }) {
  const navigate = useNavigate();
  const total = correct + incorrect;
  const pct = total ? Math.round(correct / total * 100) : 0;
  return (
    <div className="study-card" style={{ textAlign: 'center' }}>
      <div style={{ fontFamily: 'Lora, serif', fontSize: 22, fontWeight: 600, marginBottom: 8 }}>Session complete</div>
      <div style={{ fontSize: 48, fontFamily: 'Lora, serif', fontWeight: 600, color: 'var(--sage)', marginBottom: 16 }}>{pct}%</div>
      <div style={{ fontSize: 14, color: 'var(--ink-muted)', marginBottom: 24 }}>
        {correct} correct · {incorrect} incorrect · {total} cards
      </div>
      <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
        <button className="btn" onClick={() => navigate(`/deck/${deckId}`)}>Back to deck</button>
        <button className="btn btn-primary" onClick={onRestart}>Study again</button>
      </div>
    </div>
  );
}

// ── Main StudySession ─────────────────────────────────────────────────────────
export default function StudySession() {
  const { id } = useParams();
  const [mode, setMode] = useState(null); // null = picker | 'flip' | 'mcq' | 'type'
  const [cards, setCards] = useState([]);
  const [queue, setQueue] = useState([]);
  const [idx, setIdx] = useState(0);
  const [correct, setCorrect] = useState(0);
  const [incorrect, setIncorrect] = useState(0);
  const [done, setDone] = useState(false);
  const correctRef = useRef(0);
  const incorrectRef = useRef(0);

  useEffect(() => { getCards(id).then(setCards).catch(() => {}); }, [id]);

  function startStudy(m) {
    const q = shuffle(cards);
    setQueue(q);
    setIdx(0);
    setCorrect(0);
    setIncorrect(0);
    correctRef.current = 0;
    incorrectRef.current = 0;
    setDone(false);
    setMode(m);
  }

  async function handleAnswer(wasCorrect) {
    const card = queue[idx];
    await updateMastery(card.id, wasCorrect).catch(() => {});
    if (wasCorrect) { correctRef.current += 1; setCorrect(correctRef.current); }
    else { incorrectRef.current += 1; setIncorrect(incorrectRef.current); }

    if (idx + 1 >= queue.length) {
      const total = idx + 1;
      await saveSessions({
        deck_id: id,
        cards_studied: total,
        correct: correctRef.current,
        incorrect: incorrectRef.current,
        score_pct: Math.round(correctRef.current / total * 100),
      }).catch(() => {});
      setDone(true);
    } else {
      setIdx(i => i + 1);
    }
  }

  // Mode picker
  if (!mode) {
    return (
      <>
        <div className="topbar">
          <span className="topbar-title">Choose study mode</span>
        </div>
        <div className="view" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, paddingTop: 60 }}>
          {cards.length === 0 && <p style={{ color: 'var(--ink-muted)' }}>No cards in this deck yet.</p>}
          {cards.length > 0 && <>
            <button className="btn" style={{ width: 240, justifyContent: 'center', padding: '14px 20px', fontSize: 15 }} onClick={() => startStudy('flip')}>
              🃏 Flashcard flip
            </button>
            {cards.length >= 4 && (
              <button className="btn" style={{ width: 240, justifyContent: 'center', padding: '14px 20px', fontSize: 15 }} onClick={() => startStudy('mcq')}>
                ☑ Multiple choice
              </button>
            )}
            {cards.length >= 2 && (
              <button className="btn" style={{ width: 240, justifyContent: 'center', padding: '14px 20px', fontSize: 15 }} onClick={() => startStudy('type')}>
                ✎ Type the answer
              </button>
            )}
          </>}
        </div>
      </>
    );
  }

  // Done
  if (done) {
    return (
      <>
        <div className="topbar"><span className="topbar-title">Results</span></div>
        <div className="view">
          <Results correct={correct} incorrect={incorrect} deckId={id} onRestart={() => setMode(null)} />
        </div>
      </>
    );
  }

  const card = queue[idx];
  const progress = `${idx + 1} / ${queue.length}`;

  return (
    <>
      <div className="topbar">
        <span className="topbar-title">{progress}</span>
        <div className="topbar-actions">
          <button className="btn" onClick={() => setMode(null)}>✕ End session</button>
        </div>
      </div>
      <div className="view">
        {mode === 'flip' && <FlipCard key={card.id} card={card} onAnswer={handleAnswer} />}
        {mode === 'mcq' && <MCQCard key={card.id} card={card} allCards={cards} onAnswer={handleAnswer} />}
        {mode === 'type' && <TypeCard key={card.id} card={card} onAnswer={handleAnswer} />}
      </div>
    </>
  );
}
