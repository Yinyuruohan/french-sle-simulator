"""Shared Streamlit design system for the SLE simulator.

Lives outside `app.py` so that secondary pages under `pages/` can import the
CSS injector without running `app.py`'s module-level Streamlit router.
"""
import streamlit as st


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
