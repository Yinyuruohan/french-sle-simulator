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

    return {
        "session_id": session_id,
        "exam_kind": "reading_comprehension",
        "score": correct_count,
        "total": total_count,
        "percentage": round(percentage, 1),
        "level": level,
        "context_results": context_results,
        "stem_family_breakdown": breakdown,
    }
