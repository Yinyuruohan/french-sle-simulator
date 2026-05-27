"""Tests for tools/grade_reading_exam.py — deterministic grading."""
import pytest


def _make_exam(num=2):
    """Helper: minimal RC exam with `num` items."""
    return {
        "session_id": "reading_test",
        "exam_kind": "reading_comprehension",
        "contexts": [
            {
                "context_id": i + 1,
                "passage": f"Passage {i+1} content.",
                "has_signature": False,
                "questions": [
                    {
                        "question_id": i + 1,
                        "stem_family": "main_idea",
                        "question_text": "Q?",
                        "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
                        "correct_answer": "A",
                        "justification": f"Reason {i+1}.",
                        "bolded_term": None,
                    }
                ],
            }
            for i in range(num)
        ],
    }


def _make_mixed_exam(stem_families):
    """Helper: exam where each question has a specified stem_family."""
    return {
        "session_id": "reading_test",
        "exam_kind": "reading_comprehension",
        "contexts": [
            {
                "context_id": i + 1,
                "passage": f"P{i+1}",
                "has_signature": False,
                "questions": [{
                    "question_id": i + 1,
                    "stem_family": sf,
                    "question_text": "Q?",
                    "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
                    "correct_answer": "A",
                    "justification": "r",
                    "bolded_term": None,
                }],
            }
            for i, sf in enumerate(stem_families)
        ],
    }


def test_grade_all_correct():
    from tools.grade_reading_exam import grade_reading_exam
    exam = _make_exam(2)
    answers = {1: "A", 2: "A"}
    result = grade_reading_exam(exam, answers)
    assert result["score"] == 2
    assert result["total"] == 2
    assert result["percentage"] == 100.0
    assert result["level"] == "C"


def test_grade_all_wrong():
    from tools.grade_reading_exam import grade_reading_exam
    exam = _make_exam(2)
    answers = {1: "B", 2: "B"}
    result = grade_reading_exam(exam, answers)
    assert result["score"] == 0
    assert result["total"] == 2
    assert result["percentage"] == 0.0
    assert result["level"] == "Below A / Sous le niveau A"


def test_grade_missing_answer_is_incorrect():
    from tools.grade_reading_exam import grade_reading_exam
    exam = _make_exam(2)
    answers = {1: "A"}  # qid 2 missing
    result = grade_reading_exam(exam, answers)
    assert result["score"] == 1


def test_grade_level_thresholds():
    from tools.grade_reading_exam import grade_reading_exam
    # 5/5 = 100% → C
    exam5 = _make_exam(5)
    assert grade_reading_exam(exam5, {i+1: "A" for i in range(5)})["level"] == "C"
    # 4/5 = 80% → B
    answers_b = {i+1: ("A" if i < 4 else "B") for i in range(5)}
    assert grade_reading_exam(exam5, answers_b)["level"] == "B"
    # 3/5 = 60% → A
    answers_a = {i+1: ("A" if i < 3 else "B") for i in range(5)}
    assert grade_reading_exam(exam5, answers_a)["level"] == "A"
    # 2/5 = 40% → Below A
    answers_below = {i+1: ("A" if i < 2 else "B") for i in range(5)}
    assert grade_reading_exam(exam5, answers_below)["level"].startswith("Below A")


def test_grade_includes_justification_in_per_question_result():
    from tools.grade_reading_exam import grade_reading_exam
    exam = _make_exam(2)
    result = grade_reading_exam(exam, {1: "A", 2: "B"})
    q_results = result["context_results"][0]["question_results"]
    assert q_results[0]["justification"] == "Reason 1."
    assert q_results[0]["is_correct"] is True
    assert q_results[0]["user_answer"] == "A"
    assert q_results[0]["correct_answer"] == "A"


def test_grade_no_api_call():
    """grade_reading_exam does not import OpenAI."""
    import tools.grade_reading_exam as g
    assert "OpenAI" not in dir(g)


def test_breakdown_empty_when_n_less_than_4():
    from tools.grade_reading_exam import grade_reading_exam
    exam = _make_mixed_exam(["main_idea", "title", "purpose"])  # N=3
    result = grade_reading_exam(exam, {1: "A", 2: "A", 3: "A"})
    assert result["stem_family_breakdown"] == []


def test_breakdown_populated_when_n_4_or_more():
    from tools.grade_reading_exam import grade_reading_exam
    exam = _make_mixed_exam(["main_idea", "main_idea", "title", "title"])
    # 1 right + 1 wrong for main_idea; 2 right for title
    result = grade_reading_exam(exam, {1: "A", 2: "B", 3: "A", 4: "A"})
    by_family = {row["stem_family"]: row for row in result["stem_family_breakdown"]}
    assert by_family["main_idea"]["correct"] == 1
    assert by_family["main_idea"]["total"] == 2
    assert by_family["main_idea"]["pct"] == 50.0
    assert by_family["title"]["correct"] == 2
    assert by_family["title"]["total"] == 2
    assert by_family["title"]["pct"] == 100.0
