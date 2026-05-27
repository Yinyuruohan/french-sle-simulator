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

    return {
        "session_id": session_id,
        "exam_kind": "reading_comprehension",
        "score": correct_count,
        "total": total_count,
        "percentage": round(percentage, 1),
        "level": level,
        "context_results": context_results,
        "stem_family_breakdown": [],
    }
