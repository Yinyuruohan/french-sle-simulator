"""
SLE Reading Comprehension Exam Grader

Deterministically grades user answers against pre-generated correct answers
and justifications produced by tools/generate_reading_exam.py. No API call.

Works with the contexts→questions envelope where each context has exactly
one question (RC: 1 passage = 1 question).
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".tmp")
TRACKING_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "user_error_tracking.md")

LEVEL_THRESHOLDS = {"C": 0.90, "B": 0.70, "A": 0.50}


def _build_stem_family_breakdown(context_results: list) -> list:
    """Compute per-stem-family correct/total/pct from per-question results."""
    counts = {}
    for ctx in context_results:
        for q in ctx["question_results"]:
            sf = q["stem_family"]
            entry = counts.setdefault(sf, {"correct": 0, "total": 0})
            entry["total"] += 1
            if q["is_correct"]:
                entry["correct"] += 1
    return [
        {
            "stem_family": sf,
            "correct": v["correct"],
            "total": v["total"],
            "pct": round(v["correct"] / v["total"] * 100, 1) if v["total"] else 0.0,
        }
        for sf, v in counts.items()
    ]


def _determine_level(score_pct: float) -> str:
    if score_pct >= LEVEL_THRESHOLDS["C"]:
        return "C"
    if score_pct >= LEVEL_THRESHOLDS["B"]:
        return "B"
    if score_pct >= LEVEL_THRESHOLDS["A"]:
        return "A"
    return "Below A / Sous le niveau A"


def grade_reading_exam(exam: dict, user_answers: dict) -> dict:
    """Grade an RC exam deterministically using pre-generated justifications."""
    session_id = exam.get("session_id", f"reading_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

    correct_count = 0
    total_count = 0
    context_results = []

    for ctx in exam.get("contexts", []):
        ctx_result = {
            "context_id": ctx["context_id"],
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
            ctx_result["question_results"].append({
                "question_id": qid,
                "stem_family": q["stem_family"],
                "options": q["options"],
                "user_answer": user_ans,
                "correct_answer": q["correct_answer"],
                "is_correct": is_correct,
                "justification": q.get("justification", ""),
            })
        context_results.append(ctx_result)

    percentage = (correct_count / total_count * 100) if total_count > 0 else 0.0
    level = _determine_level(percentage / 100)
    breakdown = _build_stem_family_breakdown(context_results) if total_count >= 4 else []

    evaluation = {
        "session_id": session_id,
        "exam_kind": "reading_comprehension",
        "score": correct_count,
        "total": total_count,
        "percentage": round(percentage, 1),
        "level": level,
        "context_results": context_results,
        "stem_family_breakdown": breakdown,
    }

    _save_feedback_markdown(evaluation)
    _append_to_tracking(evaluation)

    return evaluation


def _save_feedback_markdown(evaluation: dict) -> None:
    """Write a per-session feedback markdown under TMP_DIR."""
    os.makedirs(TMP_DIR, exist_ok=True)
    session_id = evaluation["session_id"]
    feedback_id = session_id.replace("reading_", "reading_feedback_")
    filepath = os.path.join(TMP_DIR, f"{feedback_id}.md")

    lines = [
        "# SLE Reading Comprehension Results / Résultats — Compréhension de l'écrit",
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
        lines.append(f"## Passage {ctx_r['context_id']}")
        lines.append("")
        lines.append(f"> {ctx_r['passage']}")
        lines.append("")
        for q_r in ctx_r["question_results"]:
            status = "CORRECT ✅" if q_r["is_correct"] else "INCORRECT ❌"
            lines.append(f"### Question ({q_r['question_id']}) — {status}")
            lines.append(f"*Stem family: {q_r['stem_family']}*")
            lines.append("")
            lines.append("| | Option | |")
            lines.append("|---|---|---|")
            for letter in ["A", "B", "C", "D"]:
                opt = q_r["options"][letter]
                marker = ""
                bold = ""
                if letter == q_r["correct_answer"] and letter == q_r["user_answer"]:
                    bold = "**"
                    marker = "✅ Your answer"
                elif letter == q_r["correct_answer"]:
                    bold = "**"
                    marker = "← Correct answer"
                elif letter == q_r["user_answer"] and not q_r["is_correct"]:
                    marker = "← Your answer"
                lines.append(f"| {bold}{letter}{bold} | {bold}{opt}{bold} | {marker} |")
            lines.append("")
            lines.append(f"**Justification:** {q_r['justification']}")
            lines.append("")
        lines.append("---")
        lines.append("")

    if evaluation["stem_family_breakdown"]:
        lines.append("## Stem-family breakdown")
        lines.append("")
        lines.append("| Stem family | Correct | Total | % |")
        lines.append("|---|---:|---:|---:|")
        for row in evaluation["stem_family_breakdown"]:
            lines.append(
                f"| {row['stem_family']} | {row['correct']} | {row['total']} | {row['pct']}% |"
            )
        lines.append("")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _append_to_tracking(evaluation: dict) -> None:
    """Append incorrect items to the cumulative tracking markdown."""
    incorrect = []
    for ctx_r in evaluation["context_results"]:
        for q_r in ctx_r["question_results"]:
            if not q_r["is_correct"]:
                incorrect.append((ctx_r, q_r))
    if not incorrect:
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"\n## Session: {evaluation['session_id']}",
        f"**Date:** {timestamp}",
        f"**Mode:** Reading Comprehension",
        f"**Incorrect answers:** {len(incorrect)}",
        "",
    ]
    for ctx_r, q_r in incorrect:
        passage_excerpt = ctx_r["passage"][:200] + ("…" if len(ctx_r["passage"]) > 200 else "")
        u_letter = q_r["user_answer"]
        c_letter = q_r["correct_answer"]
        u_text = q_r["options"].get(u_letter, "(no answer)")
        c_text = q_r["options"][c_letter]
        lines.append(f"### Question ({q_r['question_id']})")
        lines.append(f"- **Stem family:** {q_r['stem_family']}")
        lines.append(f"- **Passage:** {passage_excerpt}")
        lines.append(f"- **Candidate's answer:** {u_letter}) {u_text}")
        lines.append(f"- **Correct answer:** {c_letter}) {c_text}")
        lines.append(f"- **Justification:** {q_r['justification']}")
        lines.append("")
    lines.append("---")
    lines.append("")

    if not os.path.exists(TRACKING_FILE):
        header = (
            "# SLE Exam Error Tracking / Suivi des erreurs\n\n"
            "This file logs all incorrect answers across exam sessions for adaptive learning.\n\n---\n"
        )
        with open(TRACKING_FILE, "w", encoding="utf-8") as f:
            f.write(header)

    with open(TRACKING_FILE, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))
