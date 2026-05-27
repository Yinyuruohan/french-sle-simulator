"""Tests for tools/generate_reading_exam.py — schema validation + ModelConfig wiring."""
import json
import pytest
from unittest.mock import patch, MagicMock
from tools.model_config import ModelConfig


def _valid_exam_json(num=2):
    """Helper: a syntactically valid RC exam JSON string."""
    contexts = []
    for i in range(num):
        contexts.append({
            "context_id": i + 1,
            "passage": f"Passage {i+1}.",
            "has_signature": False,
            "questions": [{
                "question_id": i + 1,
                "stem_family": "main_idea",
                "question_text": "Q?",
                "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
                "correct_answer": "A",
                "justification": "r",
                "bolded_term": None,
            }],
        })
    return json.dumps({"contexts": contexts})


def test_validate_rejects_wrong_question_count():
    from tools.generate_reading_exam import _validate_exam_schema
    exam = json.loads(_valid_exam_json(num=2))
    with pytest.raises(ValueError, match="question count"):
        _validate_exam_schema(exam, expected_n=3)


def test_validate_rejects_multi_question_context():
    from tools.generate_reading_exam import _validate_exam_schema
    exam = json.loads(_valid_exam_json(num=1))
    # add a second question to ctx 1
    exam["contexts"][0]["questions"].append(exam["contexts"][0]["questions"][0].copy())
    with pytest.raises(ValueError, match="exactly one question"):
        _validate_exam_schema(exam, expected_n=1)


def test_validate_rejects_invalid_stem_family():
    from tools.generate_reading_exam import _validate_exam_schema
    exam = json.loads(_valid_exam_json(num=1))
    exam["contexts"][0]["questions"][0]["stem_family"] = "not_a_family"
    with pytest.raises(ValueError, match="stem_family"):
        _validate_exam_schema(exam, expected_n=1)


def test_validate_rejects_missing_required_field():
    from tools.generate_reading_exam import _validate_exam_schema
    exam = json.loads(_valid_exam_json(num=1))
    del exam["contexts"][0]["questions"][0]["correct_answer"]
    with pytest.raises(ValueError, match="missing"):
        _validate_exam_schema(exam, expected_n=1)


def test_validate_rejects_bolded_term_on_non_vocabulary():
    from tools.generate_reading_exam import _validate_exam_schema
    exam = json.loads(_valid_exam_json(num=1))
    exam["contexts"][0]["questions"][0]["bolded_term"] = "something"
    # stem is main_idea, not vocabulary
    with pytest.raises(ValueError, match="bolded_term"):
        _validate_exam_schema(exam, expected_n=1)


def test_validate_rejects_vocabulary_missing_bolded_term():
    from tools.generate_reading_exam import _validate_exam_schema
    exam = json.loads(_valid_exam_json(num=1))
    exam["contexts"][0]["questions"][0]["stem_family"] = "vocabulary"
    exam["contexts"][0]["questions"][0]["bolded_term"] = None
    with pytest.raises(ValueError, match="bolded_term"):
        _validate_exam_schema(exam, expected_n=1)


def test_validate_accepts_valid_exam():
    from tools.generate_reading_exam import _validate_exam_schema
    exam = json.loads(_valid_exam_json(num=2))
    _validate_exam_schema(exam, expected_n=2)  # should not raise
