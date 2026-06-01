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
from tools.streamlit_design import inject_design_system
from tools.reading_question_bank import (
    init_db as rc_init_db,
    cache_contexts as rc_cache_contexts,
    get_bank_stats as rc_get_bank_stats,
    assemble_exam_from_cache as rc_assemble_from_cache,
    prefill_bank as rc_prefill_bank,
    upgrade_to_battle_tested as rc_upgrade_to_battle_tested,
    update_last_incorrect as rc_update_last_incorrect,
    flag_context as rc_flag_context,
)
from tools.review_reading_exam import review_reading_exam

st.set_page_config(
    page_title="SLE Reading Comprehension",
    page_icon="📖",
    layout="wide",
)
inject_design_system()
rc_init_db()


def _render_taking():
    exam = st.session_state.rc_exam
    st.title("📖 Reading Comprehension")
    st.caption(f"Session: {exam['session_id']} · {exam['num_questions']} questions")

    for ctx in exam["contexts"]:
        st.markdown(f"### Passage {ctx['context_id']}")
        st.markdown(f"> {ctx['passage']}")
        q = ctx["questions"][0]
        st.markdown(f"**Question {q['question_id']}.** {q['question_text']}")
        choices = [f"{letter}. {q['options'][letter]}" for letter in ["A", "B", "C", "D"]]
        prev = st.session_state.rc_answers.get(q["question_id"])
        try:
            idx = ["A", "B", "C", "D"].index(prev) if prev else None
        except ValueError:
            idx = None
        choice = st.radio(
            label=f"Your answer for question {q['question_id']}",
            options=choices,
            index=idx,
            key=f"rc_q_{q['question_id']}",
            label_visibility="collapsed",
        )
        if choice is not None:
            st.session_state.rc_answers[q["question_id"]] = choice.split(".", 1)[0]
        st.divider()

    missing = [
        ctx["questions"][0]["question_id"]
        for ctx in exam["contexts"]
        if ctx["questions"][0]["question_id"] not in st.session_state.rc_answers
    ]
    submit_label = (
        f"Submit ({len(missing)} unanswered — will count as wrong)"
        if missing
        else "Submit answers"
    )
    if st.button(submit_label, type="primary"):
        _go_to("evaluating")
        st.rerun()


def _render_evaluating():
    with st.spinner("Grading your answers…"):
        evaluation = grade_reading_exam(st.session_state.rc_exam, st.session_state.rc_answers)
    # Persist per-context bank metadata onto the evaluation so update/upgrade
    # can match cached contexts. grade_reading_exam doesn't carry these forward.
    bank_meta = {ctx["context_id"]: ctx for ctx in st.session_state.rc_exam.get("contexts", [])}
    for ctx_r in evaluation["context_results"]:
        orig = bank_meta.get(ctx_r["context_id"], {})
        ctx_r["bank_context_id"] = orig.get("bank_context_id")
        ctx_r["original_passage_hash"] = orig.get("original_passage_hash")

    rc_update_last_incorrect(evaluation)
    rc_upgrade_to_battle_tested(evaluation.get("session_id", ""), evaluation)

    st.session_state.rc_evaluation = evaluation
    _go_to("results")
    st.rerun()


def _render_results():
    ev = st.session_state.rc_evaluation
    st.title("📖 Results / Résultats")
    cols = st.columns(3)
    cols[0].metric("Score", f"{ev['score']} / {ev['total']}")
    cols[1].metric("Percentage", f"{ev['percentage']}%")
    cols[2].metric("Level / Niveau", ev["level"])
    st.caption("C ≥ 90% · B ≥ 70% · A ≥ 50% · Below A < 50% (unofficial estimate)")

    for ctx_r in ev["context_results"]:
        st.markdown(f"### Passage {ctx_r['context_id']}")
        st.markdown(f"> {ctx_r['passage']}")
        for q_r in ctx_r["question_results"]:
            tag = "✅ Correct" if q_r["is_correct"] else "❌ Incorrect"
            with st.expander(f"Question {q_r['question_id']} — {tag} · *{q_r['stem_family']}*", expanded=not q_r["is_correct"]):
                for letter in ["A", "B", "C", "D"]:
                    opt = q_r["options"][letter]
                    if letter == q_r["correct_answer"] and letter == q_r["user_answer"]:
                        st.markdown(f"- **{letter}. {opt}** ✅ Your answer")
                    elif letter == q_r["correct_answer"]:
                        st.markdown(f"- **{letter}. {opt}** ← Correct answer")
                    elif letter == q_r["user_answer"]:
                        st.markdown(f"- {letter}. {opt} ← Your answer")
                    else:
                        st.markdown(f"- {letter}. {opt}")
                st.markdown(f"**Justification:** {q_r['justification']}")

        bank_id = ctx_r.get("bank_context_id")
        p_hash = ctx_r.get("original_passage_hash")
        if bank_id or p_hash:
            flag_category = st.selectbox(
                "Flag quality issue / Signaler un problème",
                ["Wrong answer key", "Multiple correct answers",
                 "Unclear passage", "Bad justification", "Other"],
                key=f"rc_flag_cat_{ctx_r['context_id']}",
            )
            if st.button("Submit flag / Soumettre",
                         key=f"rc_flag_btn_{ctx_r['context_id']}"):
                rc_flag_context(bank_context_id=bank_id,
                                passage_hash=p_hash,
                                category=flag_category)
                st.success("Flag submitted. This passage will be deprioritized.")
        st.divider()

    if ev["stem_family_breakdown"]:
        st.markdown("### Stem-family breakdown")
        st.dataframe(
            ev["stem_family_breakdown"],
            hide_index=True,
            column_config={
                "stem_family": "Stem family",
                "correct": "Correct",
                "total": "Total",
                "pct": st.column_config.NumberColumn("%", format="%.1f%%"),
            },
        )

    if st.button("Try another exam"):
        for k in ["rc_exam", "rc_answers", "rc_evaluation", "rc_n", "rc_source"]:
            st.session_state.pop(k, None)
        _go_to("welcome")
        st.rerun()


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
    stats = rc_get_bank_stats()
    st.markdown(
        f"**Bank:** {stats['total_questions']} cached questions · "
        f"{stats['battle_tested']} battle-tested · "
        f"{stats['reviewed']} reviewed · "
        f"{stats['warned']} warned"
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

    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.caption("Prefill the bank with N passages (uses 1 API call).")
    with col_b:
        if st.button(f"Prefill bank ({int(n)})"):
            with st.spinner(f"Generating and reviewing {int(n)} passages…"):
                try:
                    result = rc_prefill_bank(int(n),
                                             model_config=st.session_state.rc_model_config)
                except Exception as e:
                    st.error(f"Prefill failed: {e}")
                else:
                    if result["success"]:
                        st.success(result["message"])
                    else:
                        st.error(result["message"])
            st.rerun()

    instant_disabled = stats["total_questions"] < int(n)
    col_instant, col_fresh = st.columns(2)
    with col_instant:
        if st.button(
            "Instant exam (from bank)",
            use_container_width=True,
            disabled=instant_disabled,
            help=("Not enough cached questions — prefill the bank or generate fresh."
                  if instant_disabled else None),
        ):
            st.session_state.rc_n = int(n)
            st.session_state.rc_source = "cache"
            _go_to("generating")
            st.rerun()
    with col_fresh:
        if st.button("Generate fresh (API)", type="primary", use_container_width=True):
            st.session_state.rc_n = int(n)
            st.session_state.rc_source = "fresh"
            _go_to("generating")
            st.rerun()


def _render_generating():
    n = st.session_state.get("rc_n", 5)
    source = st.session_state.get("rc_source", "fresh")
    exam = None

    # Cache path — only when the user explicitly chose Instant
    if source == "cache":
        cache_result = rc_assemble_from_cache(n)
        cached_exam = cache_result["exam"]
        if cached_exam is not None and cached_exam["num_questions"] >= n:
            exam = cached_exam
        else:
            st.error("Not enough cached questions. Prefill the bank or use Generate fresh.")
            if st.button("Back to setup"):
                _go_to("welcome")
                st.rerun()
            return

    # Fresh generation path
    if exam is None:
        with st.spinner(f"Generating {n}-question Reading Comprehension exam…"):
            try:
                fresh = generate_reading_exam(n,
                                              model_config=st.session_state.rc_model_config)
            except Exception as e:
                st.error(f"Generation failed: {e}")
                if st.button("Retry"):
                    _go_to("welcome")
                    st.rerun()
                return

            # Rule-based review + cache split (no API call here — reviewer is rule-based)
            review = review_reading_exam(fresh)
            critical_ids = {f["context_id"] for f in review["flagged_questions"]
                            if f["severity"] == "critical"}
            warned_ids = {f["context_id"] for f in review["flagged_questions"]
                          if f["severity"] == "warning"}
            clean_contexts = [c for c in fresh["contexts"] if c["context_id"] not in critical_ids]
            warned_contexts = [c for c in clean_contexts if c["context_id"] in warned_ids]
            reviewed_contexts = [c for c in clean_contexts if c["context_id"] not in warned_ids]
            if reviewed_contexts:
                rc_cache_contexts(dict(fresh, contexts=reviewed_contexts), status="reviewed")
            if warned_contexts:
                rc_cache_contexts(dict(fresh, contexts=warned_contexts), status="warned")

            # Serve the fresh exam as-is (including any critically-flagged contexts,
            # so the user gets the N items they asked for; only the bank is selective).
            exam = fresh

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
elif stage == "taking":
    _render_taking()
elif stage == "evaluating":
    _render_evaluating()
elif stage == "results":
    _render_results()
