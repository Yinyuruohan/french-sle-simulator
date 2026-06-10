// Wrapper around the browser Web Speech API (speechSynthesis).
// Voice preference: fr-CA > fr-FR > any fr-* > browser default with lang=fr-FR.

let voicesCache = [];

export function isSupported() {
  return typeof window !== 'undefined' && 'speechSynthesis' in window;
}

function refreshVoices() {
  voicesCache = window.speechSynthesis.getVoices();
}

if (isSupported()) {
  refreshVoices(); // often empty on first call in Chrome; voiceschanged fills it
  window.speechSynthesis.addEventListener('voiceschanged', refreshVoices);
}

function pickFrenchVoice() {
  const voices = voicesCache.length ? voicesCache : window.speechSynthesis.getVoices();
  const byLang = prefix => voices.find(v => v.lang.toLowerCase().startsWith(prefix));
  return byLang('fr-ca') || byLang('fr-fr') || byLang('fr') || null;
}

export function speak(text) {
  if (!isSupported() || !text || !text.trim()) return;
  window.speechSynthesis.cancel(); // rapid clicks restart cleanly
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = 'fr-FR';
  const voice = pickFrenchVoice();
  if (voice) {
    utterance.voice = voice;
    utterance.lang = voice.lang;
  }
  window.speechSynthesis.speak(utterance);
}

export function stop() {
  if (isSupported()) window.speechSynthesis.cancel();
}
