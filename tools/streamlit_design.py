"""Shared Streamlit design system for the SLE simulator.

Lives outside `app.py` so that secondary pages under `pages/` can import the
CSS injector without running `app.py`'s module-level Streamlit router.
"""
import streamlit as st

from tools.flashcard_db import add_to_inbox


def inject_design_system() -> None:
    """Inject global design system CSS matching the landing page aesthetic."""
    st.html("""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

      /* ── Layout: centered at 730px ── */
      section[data-testid="stMain"] .stMainBlockContainer {
        max-width: 730px !important;
        margin-left: auto !important;
        margin-right: auto !important;
      }

      /* ── Global font & background ── */
      html, body, section[data-testid="stMain"] {
        font-family: 'Plus Jakarta Sans', -apple-system, sans-serif !important;
      }
      section[data-testid="stMain"] {
        background: #f0f6ff !important;
      }
      .stMainBlockContainer {
        background: #f0f6ff !important;
      }

      /* ── Headings ── */
      h1 {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 28px !important;
        font-weight: 800 !important;
        color: #0f172a !important;
        letter-spacing: -0.02em !important;
        margin-bottom: 4px !important;
      }
      h2 {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 20px !important;
        font-weight: 700 !important;
        color: #0f172a !important;
        letter-spacing: -0.01em !important;
      }
      h3 {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 15px !important;
        font-weight: 700 !important;
        color: #1e293b !important;
      }
      h4 {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 14px !important;
        font-weight: 600 !important;
        color: #334155 !important;
      }
      p, li, label, .stMarkdown {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        color: #334155 !important;
        font-size: 14px !important;
        line-height: 1.65 !important;
      }

      /* ── Divider ── */
      hr {
        border-color: #e2e8f0 !important;
        margin: 16px 0 !important;
      }

      /* ── Primary button ── */
      div.stButton > button[kind="primary"],
      div.stButton > button[data-testid="baseButton-primary"],
      div.stFormSubmitButton > button[kind="primaryFormSubmit"],
      div.stFormSubmitButton > button[data-testid="baseButton-primaryFormSubmit"] {
        background: #2563eb !important;
        border-color: #2563eb !important;
        color: white !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        border-radius: 10px !important;
        padding: 10px 20px !important;
        transition: background 0.2s, box-shadow 0.2s !important;
        box-shadow: 0 2px 8px rgba(37,99,235,0.2) !important;
      }
      div.stButton > button[kind="primary"]:hover,
      div.stButton > button[data-testid="baseButton-primary"]:hover,
      div.stFormSubmitButton > button:hover {
        background: #1d4ed8 !important;
        border-color: #1d4ed8 !important;
        box-shadow: 0 4px 14px rgba(37,99,235,0.35) !important;
      }

      /* ── Secondary button ── */
      div.stButton > button[kind="secondary"],
      div.stButton > button[data-testid="baseButton-secondary"] {
        background: white !important;
        border: 1.5px solid #e2e8f0 !important;
        color: #334155 !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        border-radius: 10px !important;
        padding: 10px 20px !important;
        transition: border-color 0.2s, box-shadow 0.2s !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
      }
      div.stButton > button[kind="secondary"]:hover,
      div.stButton > button[data-testid="baseButton-secondary"]:hover {
        border-color: #2563eb !important;
        color: #2563eb !important;
        box-shadow: 0 2px 8px rgba(37,99,235,0.12) !important;
      }

      /* ── Expanders (context blocks) ── */
      div[data-testid="stExpander"] {
        background: white !important;
        border: 1.5px solid #e2e8f0 !important;
        border-radius: 12px !important;
        box-shadow: 0 2px 8px rgba(37,99,235,0.06) !important;
        margin-bottom: 12px !important;
        overflow: hidden !important;
      }
      div[data-testid="stExpander"] summary {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        color: #0f172a !important;
        padding: 14px 16px !important;
      }
      div[data-testid="stExpander"] summary:hover {
        color: #2563eb !important;
      }

      /* ── Form container ── */
      div[data-testid="stForm"] {
        background: white !important;
        border: 1.5px solid #e2e8f0 !important;
        border-radius: 12px !important;
        padding: 20px !important;
        box-shadow: 0 2px 8px rgba(37,99,235,0.05) !important;
      }

      /* ── Radio buttons ── */
      div[data-testid="stRadio"] > div {
        gap: 8px !important;
      }
      div[data-testid="stRadio"] label {
        background: #f8fafc !important;
        border: 1.5px solid #e2e8f0 !important;
        border-radius: 8px !important;
        padding: 10px 14px !important;
        cursor: pointer !important;
        transition: border-color 0.15s, background 0.15s !important;
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
        font-weight: 500 !important;
        color: #334155 !important;
        width: 100% !important;
      }
      div[data-testid="stRadio"] label:hover {
        border-color: #93c5fd !important;
        background: #eff6ff !important;
      }
      div[data-testid="stRadio"] label[data-checked="true"],
      div[data-testid="stRadio"] label:has(input:checked) {
        border-color: #2563eb !important;
        background: #eff6ff !important;
        color: #1d4ed8 !important;
      }
      /* Hide default radio circle, show styled one */
      div[data-testid="stRadio"] input[type="radio"] {
        accent-color: #2563eb !important;
      }

      /* ── Metrics ── */
      div[data-testid="stMetric"] {
        background: white !important;
        border: 1.5px solid #e2e8f0 !important;
        border-radius: 12px !important;
        padding: 16px 20px !important;
        box-shadow: 0 2px 8px rgba(37,99,235,0.06) !important;
      }
      div[data-testid="stMetricLabel"] {
        font-size: 11px !important;
        font-weight: 600 !important;
        letter-spacing: 0.06em !important;
        text-transform: uppercase !important;
        color: #64748b !important;
      }
      div[data-testid="stMetricValue"] {
        font-size: 26px !important;
        font-weight: 800 !important;
        color: #0f172a !important;
        letter-spacing: -0.02em !important;
      }

      /* ── Info / Warning / Success boxes ── */
      div[data-testid="stAlert"] {
        border-radius: 10px !important;
        border-width: 1.5px !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 13.5px !important;
        font-weight: 500 !important;
      }
      div[data-testid="stAlert"][data-baseweb="notification"] {
        border-radius: 10px !important;
      }

      /* ── Number input ── */
      div[data-testid="stNumberInput"] input {
        border-radius: 8px !important;
        border: 1.5px solid #e2e8f0 !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 16px !important;
        font-weight: 600 !important;
        color: #0f172a !important;
        background: white !important;
      }
      div[data-testid="stNumberInput"] input:focus {
        border-color: #2563eb !important;
        box-shadow: 0 0 0 3px rgba(37,99,235,0.1) !important;
      }

      /* ── Text inputs ── */
      div[data-testid="stTextInput"] input,
      div[data-testid="stTextInputRootElement"] input {
        border-radius: 8px !important;
        border: 1.5px solid #e2e8f0 !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 13px !important;
        background: white !important;
      }
      div[data-testid="stTextInput"] input:focus,
      div[data-testid="stTextInputRootElement"] input:focus {
        border-color: #2563eb !important;
        box-shadow: 0 0 0 3px rgba(37,99,235,0.1) !important;
      }

      /* ── Selectbox ── */
      div[data-testid="stSelectbox"] > div > div {
        border-radius: 8px !important;
        border: 1.5px solid #e2e8f0 !important;
        background: white !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 13px !important;
      }

      /* ── Captions ── */
      div[data-testid="stCaptionContainer"],
      small, .stCaption {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 12px !important;
        color: #94a3b8 !important;
      }

      /* ── Spinner ── */
      div[data-testid="stSpinner"] p {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        color: #2563eb !important;
        font-weight: 500 !important;
      }

      /* ── Page-load fade ── */
      @keyframes pg-fade {
        from { opacity: 0; transform: translateY(10px); }
        to   { opacity: 1; transform: translateY(0); }
      }
      .stMainBlockContainer > div > div {
        animation: pg-fade 0.4s cubic-bezier(.22,1,.36,1) both;
      }
    </style>
    """)


def _timer_html(total_seconds: int, start_ts: float) -> str:
    """Return JS timer widget for st.components.v1.html(height=0).
    Injects sticky bar and modal into window.parent.document via same-origin iframe access.
    start_ts is a Unix epoch float from time.time()."""
    return f"""<script>
(function () {{
  var START_TS = {start_ts};
  var TOTAL_SECS = {total_seconds};
  var P = window.parent;
  var D = P.document;

  function cleanup() {{
    ['rc-timer-style', 'rc-timer-bar', 'rc-timer-modal'].forEach(function (id) {{
      var el = D.getElementById(id);
      if (el) el.remove();
    }});
    if (P.__rcTimerIntervalId) {{
      clearInterval(P.__rcTimerIntervalId);
      P.__rcTimerIntervalId = null;
    }}
  }}

  cleanup();
  window.addEventListener('unload', cleanup);

  var style = D.createElement('style');
  style.id = 'rc-timer-style';
  style.textContent =
    '#rc-timer-bar{{position:fixed;top:60px;left:0;width:100%;z-index:9999;' +
    'background:#2563eb;color:white;display:flex;align-items:center;' +
    'justify-content:center;gap:10px;padding:8px 16px;overflow:hidden;' +
    'font-family:"Plus Jakarta Sans",sans-serif;font-size:15px;font-weight:700;' +
    'box-shadow:0 2px 8px rgba(0,0,0,0.2);transition:background 0.5s;}}' +
    '#rc-timer-bar.urgent{{background:#dc2626;}}' +
    '#rc-timer-progress{{position:absolute;bottom:0;left:0;height:3px;' +
    'background:rgba(255,255,255,0.45);transition:width 1s linear;}}' +
    '#rc-timer-modal{{position:fixed;inset:0;z-index:10000;' +
    'background:rgba(0,0,0,0.6);display:none;align-items:center;justify-content:center;}}' +
    '#rc-timer-modal-card{{background:white;border-radius:16px;padding:32px 40px;' +
    'max-width:420px;width:90%;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,0.3);}}';
  D.head.appendChild(style);

  var bar = D.createElement('div');
  bar.id = 'rc-timer-bar';
  bar.innerHTML =
    '&#9201; <span id="rc-timer-display">--:--</span>' +
    '<div id="rc-timer-progress" style="width:100%"></div>';
  D.body.appendChild(bar);

  var modal = D.createElement('div');
  modal.id = 'rc-timer-modal';
  modal.innerHTML =
    '<div id="rc-timer-modal-card">' +
    '<div style="font-size:48px;margin-bottom:16px">&#9200;</div>' +
    '<h2 style="margin:0 0 8px;color:#0f172a;font-size:20px;font-weight:700">' +
    'Temps &eacute;coul&eacute; / Time&#39;s up</h2>' +
    '<p style="margin:0 0 24px;color:#334155;font-size:14px;line-height:1.65">' +
    'Veuillez soumettre vos r&eacute;ponses maintenant.<br>' +
    'Please submit your answers now.</p>' +
    '<button onclick="document.getElementById(\\'rc-timer-modal\\').style.display=\\'none\\'" ' +
    'style="background:#2563eb;color:white;border:none;border-radius:10px;' +
    'padding:10px 24px;font-size:14px;font-weight:600;cursor:pointer">OK</button>' +
    '</div>';
  D.body.appendChild(modal);

  function fmt(secs) {{
    var m = Math.floor(secs / 60);
    var s = Math.floor(secs % 60);
    return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
  }}

  function tick() {{
    var remaining = TOTAL_SECS - (Date.now() / 1000 - START_TS);
    var bar = D.getElementById('rc-timer-bar');
    var display = D.getElementById('rc-timer-display');
    var progress = D.getElementById('rc-timer-progress');
    var modal = D.getElementById('rc-timer-modal');
    if (!bar || !display || !progress) return;

    if (remaining <= 0) {{
      display.textContent = '00:00';
      progress.style.width = '0%';
      bar.classList.add('urgent');
      if (modal) modal.style.display = 'flex';
      clearInterval(P.__rcTimerIntervalId);
      P.__rcTimerIntervalId = null;
      return;
    }}

    display.textContent = fmt(remaining);
    progress.style.width = (remaining / TOTAL_SECS * 100) + '%';
    if (remaining <= 30) {{
      bar.classList.add('urgent');
    }} else {{
      bar.classList.remove('urgent');
    }}
  }}

  tick();
  if (TOTAL_SECS - (Date.now() / 1000 - START_TS) > 0) {{
    P.__rcTimerIntervalId = setInterval(tick, 1000);
  }}
}})();
</script>"""


def _render_vocab_note_sidebar(source: str = 'exam') -> None:
    with st.sidebar:
        st.markdown("### 📝 Vocab Note")
        note_words = st.text_area(
            "Words you don't know (one per line)",
            placeholder="atelier\nallouer\naperçu",
            key="vocab_note_input",
            height=160,
            label_visibility="collapsed"
        )
        if st.button("Save to Flashcard Inbox", type="secondary", use_container_width=True):
            words = [w.strip() for w in note_words.splitlines() if w.strip()]
            if words:
                add_to_inbox(words, source=source)
                st.success(f"Saved {len(words)} word(s) to your Flashcard Inbox")
            else:
                st.warning("No words to save — enter one word per line")
