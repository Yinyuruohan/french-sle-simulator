"""Tests for tools/evaluate_exam.py deterministic evaluation."""
import pytest


def _make_exam_with_explanations():
    """Helper: exam with pre-generated explanations."""
    return {
        "session_id": "exam_test",
        "timestamp": "2026-03-25T00:00:00",
        "num_questions": 2,
        "contexts": [{
            "context_id": 1,
            "type": "fill_in_blank",
            "passage": "Test (1) ___ and (2) ___ here.",
            "questions": [
                {
                    "question_id": 1,
                    "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
                    "correct_answer": "A",
                    "grammar_topic": "agreement",
                    "explanation": {"why_correct": "Reason 1", "grammar_rule": "Rule 1"},
                },
                {
                    "question_id": 2,
                    "options": {"A": "x", "B": "y", "C": "z", "D": "w"},
                    "correct_answer": "B",
                    "grammar_topic": "preposition",
                    "explanation": {"why_correct": "Reason 2", "grammar_rule": "Rule 2"},
                },
            ],
        }],
    }


def test_evaluate_exam_no_api_call():
    """evaluate_exam does not import or use OpenAI."""
    import tools.evaluate_exam as ev
    # OpenAI should not be imported in the module at all
    assert "OpenAI" not in dir(ev)
    # Calling evaluate_exam should work without any API setup
    from tools.evaluate_exam import evaluate_exam
    exam = _make_exam_with_explanations()
    answers = {1: "A", 2: "C"}
    result = evaluate_exam(exam, answers)
    assert result["score"] == 1
    assert result["total"] == 2


def test_evaluate_exam_deterministic_scoring():
    """evaluate_exam scores answers correctly and returns pre-generated explanations."""
    from tools.evaluate_exam import evaluate_exam

    exam = _make_exam_with_explanations()
    answers = {1: "A", 2: "C"}  # Q1 correct, Q2 incorrect

    result = evaluate_exam(exam, answers)
    assert result["score"] == 1
    assert result["total"] == 2
    assert result["percentage"] == 50.0
    assert result["level"] == "A"

    # Check explanations are from exam data
    q1 = result["context_results"][0]["question_results"][0]
    assert q1["explanation"] == {"why_correct": "Reason 1", "grammar_rule": "Rule 1"}
    q2 = result["context_results"][0]["question_results"][1]
    assert q2["explanation"] == {"why_correct": "Reason 2", "grammar_rule": "Rule 2"}


def test_evaluate_exam_no_model_config_param():
    """evaluate_exam does not require model_config parameter."""
    import inspect
    from tools.evaluate_exam import evaluate_exam
    sig = inspect.signature(evaluate_exam)
    assert "model_config" not in sig.parameters


def test_generate_explanations_removed():
    """_generate_explanations and regenerate_explanations should not exist."""
    import tools.evaluate_exam as ev
    assert not hasattr(ev, "_generate_explanations")
    assert not hasattr(ev, "regenerate_explanations")
    assert not hasattr(ev, "resave_feedback_markdown")
