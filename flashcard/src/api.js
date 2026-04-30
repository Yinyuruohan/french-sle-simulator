const BASE = '';

async function req(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const r = await fetch(BASE + path, opts);
  if (!r.ok) {
    const err = await r.json().catch(() => ({ error: r.statusText }));
    throw new Error(err.error || r.statusText);
  }
  return r.json();
}

// Decks
export const getDecks = () => req('GET', '/api/decks');
export const createDeck = (data) => req('POST', '/api/decks', data);
export const updateDeck = (id, data) => req('PUT', `/api/decks/${id}`, data);
export const deleteDeck = (id) => req('DELETE', `/api/decks/${id}`);

// Cards
export const getCards = (deckId) => req('GET', `/api/decks/${deckId}/cards`);
export const addCard = (deckId, data) => req('POST', `/api/decks/${deckId}/cards`, data);
export const updateCard = (id, data) => req('PUT', `/api/cards/${id}`, data);
export const deleteCard = (id) => req('DELETE', `/api/cards/${id}`);
export const updateMastery = (id, correct) => req('POST', `/api/cards/${id}/mastery`, { correct });

// Sessions
export const saveSessions = (data) => req('POST', '/api/sessions', data);
export const getSessions = () => req('GET', '/api/sessions');

// Inbox
export const getInbox = () => req('GET', '/api/inbox');
export const dismissInbox = (ids) => req('POST', '/api/inbox/dismiss', { ids });
export const generateFromInbox = (ids) => req('POST', '/api/inbox/generate', { ids });
export const commitInbox = (cards, deckId, ids) =>
  req('POST', '/api/inbox/commit', { cards, deck_id: deckId, ids });

// AI generation
export const aiFromTopic = (topic, count, lang = 'French') =>
  req('POST', '/api/ai/from-topic', { topic, count, lang });
export const aiFromText = (text, lang = 'French') =>
  req('POST', '/api/ai/from-text', { text, lang });
export const aiCommit = (cards, deckId) =>
  req('POST', '/api/ai/commit', { cards, deck_id: deckId });
