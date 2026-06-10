import { isSupported, speak } from '../lib/speech.js';

// Small 🔊 button that pronounces `text` in French.
// Renders nothing when the browser has no speechSynthesis.
export default function SpeakerButton({ text, className = 'icon-btn' }) {
  if (!isSupported()) return null;
  return (
    <button
      type="button"
      className={className}
      title="Écouter"
      aria-label={`Écouter « ${text} »`}
      onClick={e => { e.stopPropagation(); speak(text); }}
    >
      🔊
    </button>
  );
}
