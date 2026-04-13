"""
SLE Written Expression Exam Simulator
Simulateur d'examen d'expression écrite ELS

A Streamlit web app that simulates the Canadian federal Public Service Commission's
Second Language Evaluation (SLE) — Test of Written Expression.
"""

import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from tools.generate_exam import generate_exam, regenerate_context, resave_exam_markdown
from tools.evaluate_exam import evaluate_exam
from tools.review_exam import review_exam_quality, log_system_errors
from tools.model_config import ModelConfig, load_default_configs
from tools.question_bank import init_db, cache_contexts, upgrade_to_battle_tested, update_last_incorrect, assemble_exam_from_cache, get_bank_stats, prefill_bank, flag_context

st.set_page_config(
    page_title="SLE Written Expression Simulator",
    page_icon="📝",
    layout="wide",
)

if "stage" not in st.session_state:
    st.session_state.stage = "welcome"
if "exam" not in st.session_state:
    st.session_state.exam = None
if "evaluation" not in st.session_state:
    st.session_state.evaluation = None
if "exam_review" not in st.session_state:
    st.session_state.exam_review = None
if "model_configs" not in st.session_state:
    st.session_state.model_configs = load_default_configs()

init_db()


def go_to(stage):
    st.session_state.stage = stage


def _inject_design_system():
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


def _use_twothirds_layout():
    """Constrain the page to 2/3 of the viewport width, centered."""
    st.html("""
    <style>
      section[data-testid="stMain"] .stMainBlockContainer {
        max-width: 66.67vw !important;
        margin-left: auto !important;
        margin-right: auto !important;
      }
    </style>
    """)


# ── Welcome ──────────────────────────────────────────────────────────────────

def render_welcome():
    _use_twothirds_layout()
    st.html("""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

      * { box-sizing: border-box; margin: 0; padding: 0; }

      .lp-wrap {
        font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
        background: #f0f6ff;
        border-radius: 16px;
        overflow: hidden;
      }

      /* ── HERO ── */
      .lp-hero {
        background: linear-gradient(135deg, #e8f1ff 0%, #f0f6ff 50%, #e0edff 100%);
        padding: 48px 40px 40px;
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 32px;
        align-items: center;
        position: relative;
        overflow: hidden;
      }

      /* Decorative circles background */
      .lp-hero::before {
        content: '';
        position: absolute;
        width: 400px; height: 400px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(59,130,246,0.08) 0%, transparent 70%);
        top: -100px; right: -80px;
        pointer-events: none;
      }

      .lp-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(59,130,246,0.1);
        color: #2563eb;
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 0.04em;
        padding: 5px 12px;
        border-radius: 100px;
        margin-bottom: 20px;
        border: 1px solid rgba(59,130,246,0.2);
      }

      .lp-badge::before {
        content: '🇨🇦';
        font-size: 13px;
      }

      .lp-hero h1 {
        font-size: clamp(28px, 4vw, 44px);
        font-weight: 800;
        line-height: 1.12;
        color: #0f172a;
        margin-bottom: 8px;
        letter-spacing: -0.03em;
      }

      .lp-hero h1 .accent {
        color: #2563eb;
      }

      .lp-hero-sub {
        font-size: 15px;
        color: #475569;
        font-weight: 400;
        line-height: 1.6;
        margin-bottom: 28px;
        font-style: italic;
      }

      .lp-hero-desc {
        font-size: 15px;
        color: #334155;
        line-height: 1.65;
        margin-bottom: 28px;
        font-weight: 400;
      }

      .lp-pills {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 8px;
      }

      .lp-pill {
        display: flex;
        align-items: center;
        gap: 5px;
        background: white;
        border: 1px solid #e2e8f0;
        color: #475569;
        font-size: 12.5px;
        font-weight: 500;
        padding: 5px 12px;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        white-space: nowrap;
      }

      .lp-pill .dot {
        width: 6px; height: 6px;
        background: #2563eb;
        border-radius: 50%;
        flex-shrink: 0;
      }

      /* ── MOCK UI CARD (right side) ── */
      .lp-mock {
        background: white;
        border-radius: 16px;
        box-shadow: 0 20px 60px rgba(37,99,235,0.12), 0 4px 12px rgba(0,0,0,0.06);
        overflow: hidden;
        border: 1px solid rgba(37,99,235,0.08);
      }

      .lp-mock-header {
        background: #2563eb;
        padding: 14px 18px;
        display: flex;
        align-items: center;
        justify-content: space-between;
      }

      .lp-mock-dots {
        display: flex; gap: 5px;
      }

      .lp-mock-dots span {
        width: 8px; height: 8px;
        border-radius: 50%;
        background: rgba(255,255,255,0.4);
      }

      .lp-mock-dots span:first-child { background: rgba(255,255,255,0.7); }

      .lp-mock-title {
        color: white;
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 0.05em;
      }

      .lp-mock-body {
        padding: 18px;
      }

      .lp-mock-q {
        font-size: 12px;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 10px;
      }

      .lp-mock-passage {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px 14px;
        font-size: 13px;
        color: #1e293b;
        line-height: 1.6;
        margin-bottom: 12px;
        font-style: italic;
      }

      .lp-mock-passage .blank {
        display: inline-block;
        background: #dbeafe;
        color: #1d4ed8;
        font-weight: 700;
        font-style: normal;
        padding: 1px 8px;
        border-radius: 4px;
        font-size: 12px;
      }

      .lp-mock-options {
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin-bottom: 12px;
      }

      .lp-mock-opt {
        display: flex;
        align-items: center;
        gap: 9px;
        padding: 8px 12px;
        border-radius: 8px;
        border: 1.5px solid #e2e8f0;
        font-size: 13px;
        color: #475569;
        background: white;
        font-weight: 500;
      }

      .lp-mock-opt.selected {
        border-color: #2563eb;
        background: #eff6ff;
        color: #1d4ed8;
      }

      .lp-mock-opt .opt-letter {
        width: 22px; height: 22px;
        border-radius: 50%;
        background: #f1f5f9;
        display: flex; align-items: center; justify-content: center;
        font-size: 11px;
        font-weight: 700;
        color: #64748b;
        flex-shrink: 0;
      }

      .lp-mock-opt.selected .opt-letter {
        background: #2563eb;
        color: white;
      }

      .lp-mock-level {
        display: flex;
        gap: 6px;
        margin-top: 10px;
      }

      .lp-level-badge {
        flex: 1;
        text-align: center;
        padding: 7px 4px;
        border-radius: 8px;
        font-size: 12px;
        font-weight: 700;
        border: 1.5px solid #e2e8f0;
        color: #94a3b8;
      }

      .lp-level-badge.active {
        background: #eff6ff;
        border-color: #2563eb;
        color: #1d4ed8;
      }

      /* ── FEATURES ── */
      .lp-features {
        padding: 36px 40px 40px;
        background: white;
      }

      .lp-feat-label {
        display: inline-block;
        background: #f0f6ff;
        color: #2563eb;
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 0.06em;
        padding: 5px 14px;
        border-radius: 100px;
        margin-bottom: 18px;
        border: 1px solid rgba(37,99,235,0.15);
      }

      .lp-feat-heading {
        font-size: clamp(20px, 2.5vw, 26px);
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 24px;
        letter-spacing: -0.02em;
        line-height: 1.2;
      }

      .lp-feat-heading .accent { color: #2563eb; }

      .lp-feat-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 16px;
      }

      .lp-feat-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 22px 20px;
        transition: box-shadow 0.2s, border-color 0.2s;
      }

      .lp-feat-card:hover {
        box-shadow: 0 8px 24px rgba(37,99,235,0.1);
        border-color: rgba(37,99,235,0.2);
      }

      .lp-feat-icon {
        width: 40px; height: 40px;
        border-radius: 10px;
        display: flex; align-items: center; justify-content: center;
        font-size: 20px;
        margin-bottom: 14px;
      }

      .lp-feat-card h3 {
        font-size: 14px;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 7px;
        line-height: 1.3;
      }

      .lp-feat-card p {
        font-size: 13px;
        color: #64748b;
        line-height: 1.6;
        font-weight: 400;
      }

      /* ── DISCLAIMER ── */
      .lp-disclaimer {
        padding: 14px 40px;
        background: #f8fafc;
        border-top: 1px solid #e2e8f0;
        font-size: 12px;
        color: #94a3b8;
        text-align: center;
        font-style: italic;
        line-height: 1.5;
      }

      /* Override Streamlit primary button to match landing page blue */
      div.stButton > button[kind="primary"],
      div.stButton > button[data-testid="baseButton-primary"] {
        background: #2563eb !important;
        border-color: #2563eb !important;
        color: white !important;
        font-family: 'Plus Jakarta Sans', -apple-system, sans-serif !important;
        font-weight: 600 !important;
        font-size: 15px !important;
        border-radius: 10px !important;
        padding: 10px 24px !important;
        transition: background 0.2s, box-shadow 0.2s !important;
      }

      div.stButton > button[kind="primary"]:hover,
      div.stButton > button[data-testid="baseButton-primary"]:hover {
        background: #1d4ed8 !important;
        border-color: #1d4ed8 !important;
        box-shadow: 0 4px 14px rgba(37,99,235,0.35) !important;
      }

      /* Animations */
      @keyframes lp-up {
        from { opacity: 0; transform: translateY(18px); }
        to   { opacity: 1; transform: translateY(0); }
      }

      .lp-hero-left  { animation: lp-up 0.55s cubic-bezier(.22,1,.36,1) both; animation-delay: 0.05s; }
      .lp-mock       { animation: lp-up 0.55s cubic-bezier(.22,1,.36,1) both; animation-delay: 0.18s; }
      .lp-features   { animation: lp-up 0.55s cubic-bezier(.22,1,.36,1) both; animation-delay: 0.28s; }
    </style>

    <div class="lp-wrap">

      <!-- HERO -->
      <div class="lp-hero">
        <div class="lp-hero-left">
          <div class="lp-badge">Public Service Commission of Canada</div>
          <h1>Practice French writing<br><span class="accent">smarter</span>, not harder</h1>
          <p class="lp-hero-sub">Simulateur d'expression écrite — ÉLS / SLE</p>
          <p class="lp-hero-desc">
            AI-generated practice exams modeled on the official SLE Written Expression format.
            Get instant grammar feedback and track your progress toward levels A, B, and C.
          </p>
          <div class="lp-pills">
            <span class="lp-pill"><span class="dot"></span>Fill-in-the-blank</span>
            <span class="lp-pill"><span class="dot"></span>Error identification</span>
            <span class="lp-pill"><span class="dot"></span>2–20 questions</span>
            <span class="lp-pill"><span class="dot"></span>Instant feedback</span>
            <span class="lp-pill"><span class="dot"></span>Question bank</span>
          </div>
        </div>

        <!-- Mock UI -->
        <div class="lp-mock">
          <div class="lp-mock-header">
            <div class="lp-mock-dots">
              <span></span><span></span><span></span>
            </div>
            <span class="lp-mock-title">SLE — Question (3)</span>
            <span style="font-size:11px;color:rgba(255,255,255,0.6);font-weight:500;">3 / 10</span>
          </div>
          <div class="lp-mock-body">
            <p class="lp-mock-q">Fill in the blank</p>
            <div class="lp-mock-passage">
              Le directeur a demandé que tous les employés <span class="blank">(3) ___</span> le rapport avant vendredi.
            </div>
            <div class="lp-mock-options">
              <div class="lp-mock-opt"><span class="opt-letter">A</span> soumettent</div>
              <div class="lp-mock-opt selected"><span class="opt-letter">B</span> soumettront</div>
              <div class="lp-mock-opt"><span class="opt-letter">C</span> ont soumis</div>
              <div class="lp-mock-opt"><span class="opt-letter">D</span> soumettait</div>
            </div>
            <div class="lp-mock-level">
              <div class="lp-level-badge">A ≥50%</div>
              <div class="lp-level-badge active">B ≥70%</div>
              <div class="lp-level-badge">C ≥90%</div>
            </div>
          </div>
        </div>
      </div>

      <!-- FEATURES -->
      <div class="lp-features">
        <div class="lp-feat-label">Core Features</div>
        <p class="lp-feat-heading">Here are the <span class="accent">reasons</span> you should try</p>
        <div class="lp-feat-grid">
          <div class="lp-feat-card">
            <div class="lp-feat-icon" style="background:#eff6ff;">🎯</div>
            <h3>Realistic exam format</h3>
            <p>Two question types matching the official SLE exam: fill-in-the-blank and error identification with Canadian federal workplace passages.</p>
          </div>
          <div class="lp-feat-card">
            <div class="lp-feat-icon" style="background:#f0fdf4;">✅</div>
            <h3>Grammar practice &amp; checking</h3>
            <p>Every question includes a <em>why_correct</em> explanation and grammar rule. AI quality review validates all answers before you see them.</p>
          </div>
          <div class="lp-feat-card">
            <div class="lp-feat-icon" style="background:#fefce8;">⚡</div>
            <h3>Instant exams, anytime</h3>
            <p>Question bank cache delivers exams instantly with no API call. Pre-fill the bank once and practice offline at any time.</p>
          </div>
        </div>
      </div>

      <!-- DISCLAIMER -->
      <div class="lp-disclaimer">
        ⚠ Unofficial practice tool — not affiliated with the Public Service Commission of Canada. Results are not official. ·
        Outil non officiel — sans lien avec la Commission de la fonction publique du Canada.
      </div>

    </div>
    """)

    st.markdown("")

    if st.button("Start a writing exam / Commencer un examen d'écriture", type="primary", use_container_width=True):
        go_to("setup")
        st.rerun()


# ── Setup ────────────────────────────────────────────────────────────────────

def render_setup():
    _inject_design_system()
    st.html("""
    <div style="margin-bottom:20px">
      <span style="display:inline-flex;align-items:center;gap:6px;background:rgba(37,99,235,0.08);color:#2563eb;font-family:'Plus Jakarta Sans',sans-serif;font-size:11px;font-weight:600;letter-spacing:0.06em;padding:4px 12px;border-radius:100px;border:1px solid rgba(37,99,235,0.18);margin-bottom:10px">
        SLE Practice Tool
      </span>
      <h1 style="font-family:'Plus Jakarta Sans',sans-serif;font-size:26px;font-weight:800;color:#0f172a;letter-spacing:-0.02em;margin:0 0 4px 0">Exam Setup</h1>
      <p style="font-family:'Plus Jakarta Sans',sans-serif;font-size:13px;color:#64748b;margin:0;font-style:italic">Configuration de l'examen</p>
      <div style="height:2px;background:linear-gradient(90deg,#2563eb,rgba(37,99,235,0.1));border-radius:2px;margin-top:16px"></div>
    </div>
    """)

    num_questions = st.number_input(
        "How many questions? / Combien de questions ?",
        min_value=2,
        max_value=20,
        value=10,
        step=1,
        help="The official exam has 40 questions. / L'examen officiel comporte 40 questions."
    )

    num_fill = round(num_questions * 0.5)
    num_err = num_questions - num_fill

    st.markdown(f"""
**Your exam will include / Votre examen comprendra :**
- ~{num_fill} fill-in-the-blank questions / questions à compléter
- ~{num_err} error identification questions / questions d'identification d'erreurs
""")

    # Question bank status
    bank_stats = get_bank_stats()
    st.markdown(f"**Question bank:** {bank_stats['total_questions']} questions available "
                f"({bank_stats['battle_tested']} battle-tested, {bank_stats['reviewed']} reviewed, "
                f"{bank_stats.get('warned', 0)} warned)")

    col_prefill1, col_prefill2 = st.columns([3, 1])
    with col_prefill1:
        st.caption("Pre-filling generates questions via API (2-3 paid calls)")
    with col_prefill2:
        if st.button("Pre-fill bank", use_container_width=True):
            try:
                with st.spinner("Generating and caching questions..."):
                    result = prefill_bank(num_questions, st.session_state.model_configs)
                if result["success"]:
                    st.success(result["message"])
                    st.rerun()
                else:
                    st.warning(result["message"])
            except Exception as e:
                st.error(f"Pre-fill failed: {e}")

    with st.expander("AI model settings (optional)"):
        for tool_key, label in [("generate", "Generation"), ("evaluate", "Evaluation"), ("review", "Review")]:
            cfg = st.session_state.model_configs[tool_key]
            st.markdown(f"**{label}**")
            col1, col2, col3 = st.columns(3)
            with col1:
                model = st.text_input("Model", value=cfg.model, key=f"{tool_key}_model")
            with col2:
                base_url = st.text_input("Base URL", value=cfg.base_url, key=f"{tool_key}_base_url")
            with col3:
                api_key = st.text_input("API Key", value="", placeholder="leave blank to use .env",
                                        type="password", key=f"{tool_key}_api_key")
            # Runs on every Streamlit rerun. The 'api_key or cfg.api_key' guard prevents
            # a blank password field from overwriting a key already stored in session state.
            st.session_state.model_configs[tool_key] = ModelConfig(
                model=model,
                base_url=base_url,
                api_key=api_key or cfg.api_key,
            )

    # Check cache availability for button labels
    bank_stats = get_bank_stats()
    has_bank = bank_stats["total_questions"] > 0

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("← Back / Retour", use_container_width=True):
            go_to("welcome")
            st.rerun()
    with col2:
        bank_disabled = not has_bank
        if st.button("Instant exam (from bank)", use_container_width=True, disabled=bank_disabled):
            cache_result = assemble_exam_from_cache(num_questions)
            if cache_result["exam"] is not None:
                st.session_state.exam = cache_result["exam"]
                st.session_state.exam_review = {"passed": True, "flagged_questions": [], "summary": "Served from cache."}
                go_to("exam")
                st.rerun()
            else:
                st.warning("Not enough questions in bank. Use 'Generate fresh' instead.")
    with col3:
        if st.button("Generate fresh (API)", type="primary", use_container_width=True):
            st.session_state.generate_fresh = True
            st.session_state.requested_questions = num_questions

    # Fresh generation path (existing pipeline)
    if st.session_state.get("generate_fresh"):
        st.session_state.generate_fresh = None
        requested = st.session_state.get("requested_questions", num_questions)
        try:
            with st.spinner("Generating your exam... / Génération de votre examen en cours..."):
                exam = generate_exam(requested, model_config=st.session_state.model_configs["generate"])

            # ── Review Point 1: Exam quality ──
            with st.spinner("Reviewing exam quality... / Vérification de la qualité..."):
                review = review_exam_quality(exam, model_config=st.session_state.model_configs["review"])

            if not review["passed"]:
                # Collect critical issues grouped by context_id
                critical_issues_by_ctx = {}
                for f in review.get("flagged_questions", []):
                    if f.get("severity") == "critical":
                        cid = f.get("context_id")
                        if cid is not None:
                            critical_issues_by_ctx.setdefault(cid, []).append(f)

                if critical_issues_by_ctx:
                    regen_failures = []
                    with st.spinner("Fixing flagged questions... / Correction des questions signalées..."):
                        for ctx_id, issues in critical_issues_by_ctx.items():
                            for i, ctx in enumerate(exam["contexts"]):
                                if ctx["context_id"] == ctx_id:
                                    start_qid = ctx["questions"][0]["question_id"]

                                    try:
                                        new_ctx = regenerate_context(ctx, exam["contexts"], start_qid, issues,
                                                                     model_config=st.session_state.model_configs["generate"])
                                        exam["contexts"][i] = new_ctx
                                    except Exception as regen_err:
                                        regen_failures.append(f"Context {ctx_id}: {regen_err}")
                                    break

                        # Re-save exam markdown with corrected contexts
                        resave_exam_markdown(exam)

                        # Re-review (but don't loop again)
                        review = review_exam_quality(exam, model_config=st.session_state.model_configs["review"])

                    if regen_failures:
                        st.warning(
                            "Some questions could not be regenerated and may contain errors: "
                            + "; ".join(regen_failures),
                            icon="⚠️"
                        )

            # Log any flagged issues to system error tracking
            if review.get("flagged_questions"):
                log_system_errors(exam["session_id"], "exam_review", review)

            # Identify warned context IDs
            warned_ctx_ids = set()
            for f in review.get("flagged_questions", []):
                if f.get("severity") == "warning" and f.get("context_id"):
                    warned_ctx_ids.add(f["context_id"])

            # Cache with appropriate status
            warned_ctxs = [c for c in exam["contexts"] if c["context_id"] in warned_ctx_ids]
            clean_ctxs = [c for c in exam["contexts"] if c["context_id"] not in warned_ctx_ids]

            if clean_ctxs:
                clean_exam = dict(exam)
                clean_exam["contexts"] = clean_ctxs
                cache_contexts(clean_exam, status="reviewed")
            if warned_ctxs:
                warned_exam = dict(exam)
                warned_exam["contexts"] = warned_ctxs
                cache_contexts(warned_exam, status="warned")

            st.session_state.exam_review = review
            st.session_state.exam = exam
            go_to("exam")
            st.rerun()
        except Exception as e:
            st.error(f"Error generating exam: {e}")


# ── Exam ─────────────────────────────────────────────────────────────────────

def render_exam():
    _inject_design_system()
    exam = st.session_state.exam
    if not exam:
        go_to("welcome")
        st.rerun()
        return

    st.html(f"""
    <div style="margin-bottom:20px">
      <span style="display:inline-flex;align-items:center;gap:6px;background:rgba(37,99,235,0.08);color:#2563eb;font-family:'Plus Jakarta Sans',sans-serif;font-size:11px;font-weight:600;letter-spacing:0.06em;padding:4px 12px;border-radius:100px;border:1px solid rgba(37,99,235,0.18);margin-bottom:10px">
        {exam['num_questions']} questions
      </span>
      <h1 style="font-family:'Plus Jakarta Sans',sans-serif;font-size:26px;font-weight:800;color:#0f172a;letter-spacing:-0.02em;margin:0 0 4px 0">Exam</h1>
      <p style="font-family:'Plus Jakarta Sans',sans-serif;font-size:13px;color:#64748b;margin:0;font-style:italic">Examen · {exam['session_id']}</p>
      <div style="height:2px;background:linear-gradient(90deg,#2563eb,rgba(37,99,235,0.1));border-radius:2px;margin-top:16px"></div>
    </div>
    """)

    # Show review warnings if any
    review = st.session_state.get("exam_review")
    if review and not review["passed"]:
        warnings = [f["issue"] for f in review.get("flagged_questions", []) if f.get("severity") == "warning"]
        if warnings:
            st.warning(
                "Some questions were flagged during quality review. Results may not be fully reliable for flagged items. / "
                "Certaines questions ont été signalées lors du contrôle qualité.",
                icon="⚠️"
            )

    st.info(
        "Select the best answer for each question. / Choisissez la meilleure réponse pour chaque question.",
        icon="📋"
    )

    contexts = exam.get("contexts", [])

    # Show banner for warned cached contexts
    warned_contexts = [ctx for ctx in contexts if ctx.get("bank_status") == "warned"]
    if warned_contexts:
        st.info(
            "Some questions in this exam were flagged with minor quality warnings during generation. "
            "They may contain ambiguities. / "
            "Certaines questions ont été signalées avec des avertissements mineurs.",
            icon="ℹ️"
        )

    with st.form("exam_form"):
        user_answers = {}

        for ctx in contexts:
            ctx_type = "Fill in the blank / Remplir l'espace" if ctx["type"] == "fill_in_blank" else "Error identification / Identifier l'erreur"
            st.markdown(f"### Context {ctx['context_id']} — {ctx_type}")
            st.markdown(ctx["passage"])
            st.markdown("")

            for q in ctx.get("questions", []):
                qid = q["question_id"]
                opts = q["options"]
                options_display = [f"{letter}) {opts[letter]}" for letter in ["A", "B", "C", "D"]]

                answer = st.radio(
                    f"Question ({qid})",
                    options=["A", "B", "C", "D"],
                    format_func=lambda x, od=options_display: od[["A", "B", "C", "D"].index(x)],
                    key=f"q_{qid}",
                )
                user_answers[qid] = answer
                st.markdown("")

            st.divider()

        submitted = st.form_submit_button(
            "Submit answers / Soumettre les réponses",
            type="primary",
            use_container_width=True,
        )

        if submitted:
            st.session_state.user_answers = user_answers

    if hasattr(st.session_state, "user_answers") and st.session_state.get("user_answers"):
        answers = st.session_state.user_answers
        st.session_state.user_answers = None

        try:
            evaluation = evaluate_exam(exam, answers)

            # Propagate bank fields into evaluation results
            for ctx in exam.get("contexts", []):
                for ctx_r in evaluation.get("context_results", []):
                    if ctx_r["context_id"] == ctx["context_id"]:
                        ctx_r["bank_context_id"] = ctx.get("bank_context_id")
                        ctx_r["original_passage_hash"] = ctx.get("original_passage_hash")
                        ctx_r["bank_status"] = ctx.get("bank_status")

            # Post-evaluation triggers
            upgrade_to_battle_tested(exam["session_id"], evaluation)
            update_last_incorrect(evaluation)

            st.session_state.evaluation = evaluation
            go_to("results")
            st.rerun()
        except Exception as e:
            st.error(f"Error evaluating exam: {e}")


# ── Results ──────────────────────────────────────────────────────────────────

def render_results():
    _inject_design_system()
    evaluation = st.session_state.evaluation
    if not evaluation:
        go_to("welcome")
        st.rerun()
        return

    score = evaluation["score"]
    total = evaluation["total"]
    pct = evaluation["percentage"]
    level = evaluation["level"]
    level_color_map = {"C": "#16a34a", "B": "#d97706", "A": "#ea580c"}
    level_bg_map   = {"C": "#f0fdf4", "B": "#fffbeb", "A": "#fff7ed"}
    level_bd_map   = {"C": "#86efac", "B": "#fde68a", "A": "#fdba74"}
    lc = level_color_map.get(level, "#dc2626")
    lb = level_bg_map.get(level, "#fef2f2")
    ld = level_bd_map.get(level, "#fca5a5")

    st.html(f"""
    <div style="margin-bottom:20px">
      <span style="display:inline-flex;align-items:center;gap:6px;background:rgba(37,99,235,0.08);color:#2563eb;font-family:'Plus Jakarta Sans',sans-serif;font-size:11px;font-weight:600;letter-spacing:0.06em;padding:4px 12px;border-radius:100px;border:1px solid rgba(37,99,235,0.18);margin-bottom:10px">
        Exam complete
      </span>
      <h1 style="font-family:'Plus Jakarta Sans',sans-serif;font-size:26px;font-weight:800;color:#0f172a;letter-spacing:-0.02em;margin:0 0 4px 0">Results</h1>
      <p style="font-family:'Plus Jakarta Sans',sans-serif;font-size:13px;color:#64748b;margin:0;font-style:italic">Résultats</p>
      <div style="height:2px;background:linear-gradient(90deg,#2563eb,rgba(37,99,235,0.1));border-radius:2px;margin-top:16px;margin-bottom:20px"></div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">
        <div style="background:white;border:1.5px solid #e2e8f0;border-radius:12px;padding:16px 20px;box-shadow:0 2px 8px rgba(37,99,235,0.06)">
          <div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:10px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:#64748b;margin-bottom:6px">Score</div>
          <div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:28px;font-weight:800;color:#0f172a;letter-spacing:-0.02em">{score} <span style="font-size:16px;font-weight:500;color:#94a3b8">/ {total}</span></div>
        </div>
        <div style="background:white;border:1.5px solid #e2e8f0;border-radius:12px;padding:16px 20px;box-shadow:0 2px 8px rgba(37,99,235,0.06)">
          <div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:10px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:#64748b;margin-bottom:6px">Percentage</div>
          <div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:28px;font-weight:800;color:#0f172a;letter-spacing:-0.02em">{pct}<span style="font-size:16px;font-weight:500;color:#94a3b8">%</span></div>
        </div>
        <div style="background:{lb};border:1.5px solid {ld};border-radius:12px;padding:16px 20px;box-shadow:0 2px 8px rgba(37,99,235,0.06)">
          <div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:10px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:{lc};margin-bottom:6px">Level / Niveau</div>
          <div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:28px;font-weight:800;color:{lc};letter-spacing:-0.02em">{level}</div>
        </div>
      </div>
    </div>
    """)

    st.divider()

    with st.expander("Scoring guide / Guide de notation"):
        st.markdown("""
| Level / Niveau | Threshold / Seuil |
|---|---|
| **C** | >= 90% |
| **B** | >= 70% |
| **A** | >= 50% |
| **Below A / Sous A** | < 50% |

*Simplified proportional scoring. This is an unofficial estimate.*
*Notation proportionnelle simplifiée. Ceci est une estimation non officielle.*
""")

    # Build set of flagged explanation question IDs from exam review
    exam_review = st.session_state.get("exam_review")
    flagged_expl_ids = {}
    if exam_review:
        for f in exam_review.get("flagged_questions", []):
            if f.get("category") in ("incorrect_rule", "wrong_reasoning",
                                      "misleading_explanation", "hallucinated_rule",
                                      "inconsistent_with_question"):
                qid = f.get("question_id")
                if qid is not None:
                    flagged_expl_ids[qid] = f

    # Per-context results
    st.markdown("## Detailed Results / Résultats détaillés")

    for ctx_r in evaluation["context_results"]:
        ctx_type = "Fill in the blank" if ctx_r["type"] == "fill_in_blank" else "Error identification"

        ctx_correct = sum(1 for q in ctx_r["question_results"] if q["is_correct"])
        ctx_total = len(ctx_r["question_results"])

        with st.expander(
            f"Context {ctx_r['context_id']} — {ctx_type} ({ctx_correct}/{ctx_total})",
            expanded=any(not q["is_correct"] for q in ctx_r["question_results"])
        ):
            if ctx_r.get("bank_status") == "warned":
                st.caption("This question was flagged during quality review (warning) / "
                           "Cette question a été signalée lors du contrôle qualité (avertissement)")
            st.markdown(ctx_r["passage"])
            st.markdown("")

            for q_r in ctx_r["question_results"]:
                is_correct = q_r["is_correct"]
                icon = "✅" if is_correct else "❌"

                st.markdown(f"#### {icon} Question ({q_r['question_id']}) — *{q_r['grammar_topic']}*")

                opts = q_r["options"]
                for letter in ["A", "B", "C", "D"]:
                    opt_text = opts[letter]

                    if letter == q_r["correct_answer"] and letter == q_r["user_answer"]:
                        st.markdown(f"**{letter}) {opt_text}** ✅")
                    elif letter == q_r["correct_answer"]:
                        st.markdown(f"**{letter}) {opt_text}** ← Correct answer / Bonne réponse")
                    elif letter == q_r["user_answer"] and not is_correct:
                        st.markdown(f"~~{letter}) {opt_text}~~ ❌ Your answer / Votre réponse")
                    else:
                        st.markdown(f"{letter}) {opt_text}")

                # Show explanation for all questions
                expl = q_r.get("explanation")
                if expl:
                    st.markdown("---")
                    if isinstance(expl, dict):
                        st.markdown(f"**Why correct:** {expl.get('why_correct', 'N/A')}")
                        st.markdown(f"**Grammar rule:** {expl.get('grammar_rule', 'N/A')}")
                    else:
                        st.markdown(f"**Explanation:** {expl}")

                    # Show warning if this explanation was flagged
                    qid = q_r["question_id"]
                    if qid in flagged_expl_ids:
                        flag_severity = flagged_expl_ids[qid].get("severity")
                        if flag_severity == "critical":
                            st.warning(
                                "This explanation may be inaccurate — it was flagged as potentially incorrect during quality review. "
                                "Please verify independently. / "
                                "Cette explication pourrait être inexacte — elle a été signalée lors du contrôle qualité. "
                                "Veuillez vérifier de manière indépendante.",
                                icon="⚠️"
                            )
                        elif flag_severity == "warning":
                            st.caption(
                                "Note: This explanation was flagged during quality review and may be imprecise. / "
                                "Cette explication a été signalée et pourrait manquer de précision."
                            )

                st.markdown("")

            # Per-context flag UI
            st.markdown("---")
            flag_category = st.selectbox(
                "Flag quality issue / Signaler un problème",
                ["Wrong answer key", "Multiple correct answers", "Unclear passage",
                 "Bad explanation", "Other"],
                key=f"flag_cat_{ctx_r['context_id']}",
            )
            if st.button("Submit flag / Soumettre", key=f"flag_btn_{ctx_r['context_id']}"):
                bank_ctx_id = ctx_r.get("bank_context_id")
                p_hash = ctx_r.get("original_passage_hash")
                if bank_ctx_id or p_hash:
                    flag_context(bank_context_id=bank_ctx_id, passage_hash=p_hash, category=flag_category)
                    st.success("Flag submitted. This context will be deprioritized in future exams. / "
                               "Signalement soumis. Ce contexte sera déprioritisé.")
                else:
                    st.warning("Cannot flag this context (not yet in the question bank). / "
                               "Impossible de signaler ce contexte (pas encore dans la banque).")

    st.divider()

    st.info(
        "Exam and feedback saved to `.tmp/` folder. / "
        "L'examen et les résultats ont été sauvegardés dans le dossier `.tmp/`.",
        icon="💾"
    )

    if st.button("Start a new exam / Recommencer un examen", type="primary", use_container_width=True):
        st.session_state.exam = None
        st.session_state.evaluation = None
        st.session_state.exam_review = None
        go_to("welcome")
        st.rerun()


# ── Router ───────────────────────────────────────────────────────────────────

stage = st.session_state.stage

if stage == "welcome":
    render_welcome()
elif stage == "setup":
    render_setup()
elif stage == "exam":
    render_exam()
elif stage == "results":
    render_results()
else:
    go_to("welcome")
    st.rerun()
