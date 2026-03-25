"""
SLE Written Expression Exam Evaluator

Grades user answers against the answer key deterministically using pre-generated
explanations embedded in the exam data. Computes SLE level and logs errors to the
persistent tracking file.

Works with the contexts→questions structure where each question uses A/B/C/D.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime

TMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".tmp")
TRACKING_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "user_error_tracking.md")

LEVEL_THRESHOLDS = {
    "C": 0.90,
    "B": 0.70,
    "A": 0.50,
}


def _determine_level(score_pct: float) -> str:
    if score_pct >= LEVEL_THRESHOLDS["C"]:
        return "C"
    elif score_pct >= LEVEL_THRESHOLDS["B"]:
        return "B"
    elif score_pct >= LEVEL_THRESHOLDS["A"]:
        return "A"
    else:
        return "Below A / Sous le niveau A"


def append_to_tracking(session_id: str, incorrect_items: list, explanations: dict):
    """Append incorrect answers to the persistent tracking file."""
    if not incorrect_items:
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"\n## Session: {session_id}",
        f"**Date:** {timestamp}",
        f"**Incorrect answers:** {len(incorrect_items)}",
        "",
    ]

    for item in incorrect_items:
        q = item["question"]
        qid = q["question_id"]
        opts = q["options"]
        expl = explanations.get(qid, {})

        lines.append(f"### Question ({qid})")
        lines.append(f"- **Passage:** {item['passage']}")
        lines.append(f"- **Candidate's answer:** {item['user_answer']}) {opts[item['user_answer']]}")
        lines.append(f"- **Correct answer:** {q['correct_answer']}) {opts[q['correct_answer']]}")
        lines.append(f"- **Error category:** {q['grammar_topic']}")
        if isinstance(expl, dict):
            lines.append(f"- **Why correct:** {expl.get('why_correct', 'N/A')}")
            lines.append(f"- **Grammar rule:** {expl.get('grammar_rule', 'N/A')}")
        else:
            lines.append(f"- **Explanation:** {expl}")
        lines.append("")

    lines.append("---")
    lines.append("")

    if not os.path.exists(TRACKING_FILE):
        header = "# SLE Exam Error Tracking / Suivi des erreurs\n\nThis file logs all incorrect answers across exam sessions for adaptive learning.\n\n---\n"
        with open(TRACKING_FILE, "w", encoding="utf-8") as f:
            f.write(header)

    with open(TRACKING_FILE, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))


def evaluate_exam(exam: dict, user_answers: dict) -> dict:
    """Evaluate user answers deterministically using pre-generated explanations."""
    session_id = exam.get("session_id", f"exam_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

    correct_count = 0
    total_count = 0
    incorrect_items = []
    context_results = []
    explanations = {}

    for ctx in exam.get("contexts", []):
        ctx_result = {
            "context_id": ctx["context_id"],
            "type": ctx["type"],
            "passage": ctx["passage"],
            "question_results": [],
        }

        for q in ctx.get("questions", []):
            qid = q["question_id"]
            user_ans = user_answers.get(qid, "")
            is_correct = user_ans == q["correct_answer"]
            total_count += 1

            if is_correct:
                correct_count += 1

            expl = q.get("explanation")
            q_result = {
                "question_id": qid,
                "grammar_topic": q["grammar_topic"],
                "options": q["options"],
                "user_answer": user_ans,
                "correct_answer": q["correct_answer"],
                "is_correct": is_correct,
                "explanation": expl,
            }
            ctx_result["question_results"].append(q_result)
            explanations[qid] = expl

            if not is_correct:
                incorrect_items.append({
                    "question": q,
                    "passage": ctx["passage"],
                    "user_answer": user_ans,
                })

        context_results.append(ctx_result)

    percentage = (correct_count / total_count * 100) if total_count > 0 else 0
    level = _determine_level(percentage / 100)

    evaluation = {
        "session_id": session_id,
        "score": correct_count,
        "total": total_count,
        "percentage": round(percentage, 1),
        "level": level,
        "context_results": context_results,
    }

    _save_feedback_markdown(evaluation)
    append_to_tracking(session_id, incorrect_items, explanations)

    return evaluation


def _save_feedback_markdown(evaluation: dict):
    """Save evaluation feedback as a clean, readable markdown file in .tmp/"""
    os.makedirs(TMP_DIR, exist_ok=True)

    session_id = evaluation["session_id"]
    feedback_id = session_id.replace("exam_", "feedback_")
    filepath = os.path.join(TMP_DIR, f"{feedback_id}.md")

    lines = [
        "# SLE Exam Results / Résultats de l'examen ELS",
        "",
        f"**Session:** {session_id}",
        f"**Score:** {evaluation['score']} / {evaluation['total']} ({evaluation['percentage']}%)",
        f"**Level / Niveau:** {evaluation['level']}",
        "",
        "> C >= 90% | B >= 70% | A >= 50% | Below A < 50%",
        "> *Unofficial estimate / Estimation non officielle*",
        "",
        "---",
        "",
    ]

    for ctx_r in evaluation["context_results"]:
        ctx_type = "Fill in the blank" if ctx_r["type"] == "fill_in_blank" else "Error identification"
        lines.append(f"## Context {ctx_r['context_id']} — {ctx_type}")
        lines.append("")
        lines.append(ctx_r["passage"])
        lines.append("")

        for q_r in ctx_r["question_results"]:
            status = "CORRECT ✅" if q_r["is_correct"] else "INCORRECT ❌"
            lines.append(f"### Question ({q_r['question_id']}) — {status}")
            lines.append(f"*Grammar topic: {q_r['grammar_topic']}*")
            lines.append("")

            # Options table
            lines.append("| | Option | |")
            lines.append("|---|---|---|")
            opts = q_r["options"]
            for letter in ["A", "B", "C", "D"]:
                opt_text = opts[letter]
                marker = ""
                bold_start = ""
                bold_end = ""

                if letter == q_r["correct_answer"] and letter == q_r["user_answer"]:
                    bold_start = "**"
                    bold_end = "**"
                    marker = "✅ Your answer"
                elif letter == q_r["correct_answer"]:
                    bold_start = "**"
                    bold_end = "**"
                    marker = "← Correct answer"
                elif letter == q_r["user_answer"] and not q_r["is_correct"]:
                    marker = "← Your answer"

                lines.append(f"| {bold_start}{letter}{bold_end} | {bold_start}{opt_text}{bold_end} | {marker} |")

            lines.append("")

            # Explanation for all questions
            expl = q_r.get("explanation")
            if expl:
                if isinstance(expl, dict):
                    lines.append(f"**Why correct:** {expl.get('why_correct', 'N/A')}")
                    lines.append("")
                    lines.append(f"**Grammar rule:** {expl.get('grammar_rule', 'N/A')}")
                else:
                    lines.append(f"**Explanation:** {expl}")
                lines.append("")

        lines.append("---")
        lines.append("")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return filepath
