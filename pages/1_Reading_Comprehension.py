"""
SLE Reading Comprehension Simulator — Streamlit page.

Auto-discovered by Streamlit (lives under pages/). Sidebar entry appears
alongside the Written Expression home page.
"""
import os
import sys
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.generate_reading_exam import generate_reading_exam
from tools.grade_reading_exam import grade_reading_exam
from tools.model_config import load_default_configs
from app import _inject_design_system

st.set_page_config(
    page_title="SLE Reading Comprehension",
    page_icon="📖",
    layout="wide",
)
_inject_design_system()


def _init_state():
    defaults = {
        "rc_stage": "welcome",
        "rc_exam": None,
        "rc_answers": {},
        "rc_evaluation": None,
        "rc_model_config": load_default_configs()["reading"],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _go_to(stage: str) -> None:
    st.session_state.rc_stage = stage


def _render_welcome():
    st.title("📖 SLE Reading Comprehension")
    st.caption("Compréhension de l'écrit — Mock Exam")
    st.write(
        "Practice the Canadian federal SLE Reading Comprehension test. "
        "Pick a length, then generate an exam in administrative French."
    )
    n = st.number_input(
        "Number of questions",
        min_value=2,
        max_value=30,
        value=5,
        step=1,
        key="rc_num_questions",
    )

    cfg = st.session_state.rc_model_config
    with st.expander("AI model settings"):
        st.caption("Set via `READING_*` env vars (falls back to `DEEPSEEK_*`).")
        new_model = st.text_input("Model", value=cfg.model, key="rc_cfg_model")
        new_base = st.text_input("Base URL", value=cfg.base_url, key="rc_cfg_base")
        masked = ("•" * 6 + cfg.api_key[-4:]) if cfg.api_key else "(missing)"
        st.text(f"API key: {masked}")
        if new_model != cfg.model or new_base != cfg.base_url:
            cfg.model = new_model
            cfg.base_url = new_base

    if st.button("Generate exam", type="primary"):
        st.session_state.rc_n = int(n)
        _go_to("generating")
        st.rerun()


def _render_generating():
    n = st.session_state.get("rc_n", 5)
    with st.spinner(f"Generating {n}-question Reading Comprehension exam…"):
        try:
            exam = generate_reading_exam(n, model_config=st.session_state.rc_model_config)
        except Exception as e:
            st.error(f"Generation failed: {e}")
            if st.button("Retry"):
                _go_to("welcome")
                st.rerun()
            return
    st.session_state.rc_exam = exam
    st.session_state.rc_answers = {}
    _go_to("taking")
    st.rerun()


_init_state()
stage = st.session_state.rc_stage
if stage == "welcome":
    _render_welcome()
elif stage == "generating":
    _render_generating()
else:
    st.write(f"Stage `{stage}` not implemented yet.")
