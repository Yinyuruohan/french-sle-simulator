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
if "model_configs" not in st.session_state:
    st.session_state.model_configs = load_default_configs()

init_db()


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

    # Build set of flagged explanation question IDs from exam review
    exam_review = st.session_state.get("exam_review")
    flagged_expl_ids = {}
    if exam_review:
        for f in exam_review.get("flagged_questions", []):
            if f.get("category") in ("incorrect_rule", "wrong_reasoning",
                                      "misleading_explanation", "hallucinated_rule",
                                      "inconsistent_with_question"):
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
