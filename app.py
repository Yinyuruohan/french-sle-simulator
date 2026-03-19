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
from tools.evaluate_exam import evaluate_exam, regenerate_explanations, resave_feedback_markdown
from tools.review_exam import review_exam_quality, review_feedback_quality, log_system_errors
from tools.model_config import ModelConfig, load_default_configs

st.set_page_config(
    page_title="SLE Written Expression Simulator",
    page_icon="📝",
    layout="centered",
)

if "stage" not in st.session_state:
    st.session_state.stage = "welcome"
if "exam" not in st.session_state:
    st.session_state.exam = None
if "evaluation" not in st.session_state:
    st.session_state.evaluation = None
if "exam_review" not in st.session_state:
    st.session_state.exam_review = None
if "feedback_review" not in st.session_state:
    st.session_state.feedback_review = None
if "model_configs" not in st.session_state:
    st.session_state.model_configs = load_default_configs()


def go_to(stage):
    st.session_state.stage = stage


# ── Welcome ──────────────────────────────────────────────────────────────────

def render_welcome():
    st.title("SLE Written Expression Simulator")
    st.markdown("### Simulateur d'expression écrite — Évaluation de langue seconde")
    st.divider()

    st.markdown("""
**English:** This tool simulates the Canadian federal Public Service Commission's
Second Language Evaluation (SLE) — Test of Written Expression. It generates
practice questions modeled on the official exam format.

**Français :** Cet outil simule le Test d'expression écrite de l'Évaluation de
langue seconde (ELS) de la Commission de la fonction publique du Canada.
Il génère des questions de pratique selon le format de l'examen officiel.
""")

    st.warning(
        "**Disclaimer / Avertissement:** This is an unofficial practice tool. Results are not official. / "
        "Cet outil de pratique n'est pas officiel. Les résultats ne sont pas officiels.",
        icon="⚠️"
    )

    st.divider()

    if st.button("Start a writing exam / Commencer un examen d'écriture", type="primary", use_container_width=True):
        go_to("setup")
        st.rerun()


# ── Setup ────────────────────────────────────────────────────────────────────

def render_setup():
    st.title("Exam Setup / Configuration de l'examen")
    st.divider()

    num_questions = st.number_input(
        "How many questions? / Combien de questions ?",
        min_value=5,
        max_value=40,
        value=10,
        step=5,
        help="The official exam has 40 questions. / L'examen officiel comporte 40 questions."
    )

    num_fill = round(num_questions * 0.5)
    num_err = num_questions - num_fill

    st.markdown(f"""
**Your exam will include / Votre examen comprendra :**
- ~{num_fill} fill-in-the-blank questions / questions à compléter
- ~{num_err} error identification questions / questions d'identification d'erreurs
""")

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

    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Back / Retour", use_container_width=True):
            go_to("welcome")
            st.rerun()
    with col2:
        if st.button("Generate exam / Générer l'examen", type="primary", use_container_width=True):
            try:
                with st.spinner("Generating your exam... / Génération de votre examen en cours..."):
                    exam = generate_exam(num_questions, model_config=st.session_state.model_configs["generate"])

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

                st.session_state.exam_review = review
                st.session_state.exam = exam
                go_to("exam")
                st.rerun()
            except Exception as e:
                st.error(f"Error generating exam: {e}")


# ── Exam ─────────────────────────────────────────────────────────────────────

def render_exam():
    exam = st.session_state.exam
    if not exam:
        go_to("welcome")
        st.rerun()
        return

    st.title("Exam / Examen")
    st.markdown(f"**Session:** {exam['session_id']} | **Questions:** {exam['num_questions']}")
    st.divider()

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
            with st.spinner("Evaluating your answers... / Évaluation de vos réponses en cours..."):
                evaluation = evaluate_exam(exam, answers, model_config=st.session_state.model_configs["evaluate"])

            # ── Review Point 2: Feedback quality ──
            has_explanations = any(
                q_r.get("explanation")
                for ctx_r in evaluation["context_results"]
                for q_r in ctx_r["question_results"]
            )

            if has_explanations:
                with st.spinner("Verifying feedback quality... / Vérification des explications..."):
                    feedback_review = review_feedback_quality(evaluation, model_config=st.session_state.model_configs["review"])

                if not feedback_review["passed"]:
                    # Collect critical flagged question IDs
                    critical_qids = set(
                        f["question_id"] for f in feedback_review.get("flagged_explanations", [])
                        if f.get("severity") == "critical"
                    )

                    if critical_qids:
                        # Build a lookup: question_id -> flagged issue dict
                        flag_lookup = {}
                        for f in feedback_review.get("flagged_explanations", []):
                            if f.get("severity") == "critical":
                                flag_lookup[f["question_id"]] = f

                        regen_failures = []
                        with st.spinner("Regenerating flagged explanations... / Régénération des explications..."):
                            # Build incorrect_items with previous explanation + reviewer feedback
                            items_to_regen = []
                            for ctx in exam.get("contexts", []):
                                for q in ctx.get("questions", []):
                                    if q["question_id"] in critical_qids:
                                        user_ans = answers.get(q["question_id"], "")
                                        if user_ans != q["correct_answer"]:
                                            # Find the current (bad) explanation
                                            prev_expl = None
                                            for ctx_r in evaluation["context_results"]:
                                                for q_r in ctx_r["question_results"]:
                                                    if q_r["question_id"] == q["question_id"]:
                                                        prev_expl = q_r.get("explanation")
                                                        break

                                            items_to_regen.append({
                                                "question": q,
                                                "passage": ctx["passage"],
                                                "user_answer": user_ans,
                                                "previous_explanation": prev_expl,
                                                "flagged_issue": flag_lookup.get(q["question_id"]),
                                            })

                            if items_to_regen:
                                try:
                                    new_expls = regenerate_explanations(items_to_regen, model_config=st.session_state.model_configs["evaluate"])

                                    # Replace explanations in evaluation
                                    for ctx_r in evaluation["context_results"]:
                                        for q_r in ctx_r["question_results"]:
                                            if q_r["question_id"] in new_expls:
                                                q_r["explanation"] = new_expls[q_r["question_id"]]

                                    # Re-save feedback markdown
                                    resave_feedback_markdown(evaluation)

                                    # Re-review once (don't loop)
                                    feedback_review = review_feedback_quality(evaluation, model_config=st.session_state.model_configs["review"])
                                except Exception as regen_err:
                                    regen_failures.append(str(regen_err))

                        if regen_failures:
                            st.warning(
                                "Some explanations could not be regenerated and may be inaccurate: "
                                + "; ".join(regen_failures),
                                icon="⚠️"
                            )

                # Log any flagged issues to system error tracking
                if feedback_review.get("flagged_explanations"):
                    log_system_errors(exam["session_id"], "feedback_review", feedback_review)

                st.session_state.feedback_review = feedback_review
            else:
                st.session_state.feedback_review = None

            st.session_state.evaluation = evaluation
            go_to("results")
            st.rerun()
        except Exception as e:
            st.error(f"Error evaluating exam: {e}")


# ── Results ──────────────────────────────────────────────────────────────────

def render_results():
    evaluation = st.session_state.evaluation
    if not evaluation:
        go_to("welcome")
        st.rerun()
        return

    st.title("Results / Résultats")
    st.divider()

    # Score summary
    score = evaluation["score"]
    total = evaluation["total"]
    pct = evaluation["percentage"]
    level = evaluation["level"]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Score", f"{score} / {total}")
    with col2:
        st.metric("Percentage", f"{pct}%")
    with col3:
        level_color = {"C": "🟢", "B": "🟡", "A": "🟠"}.get(level, "🔴")
        st.metric("Level / Niveau", f"{level_color} {level}")

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

    # Build set of flagged explanation question IDs
    feedback_review = st.session_state.get("feedback_review")
    flagged_expl_ids = {}
    if feedback_review:
        for f in feedback_review.get("flagged_explanations", []):
            flagged_expl_ids[f["question_id"]] = f

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
        st.session_state.feedback_review = None
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
