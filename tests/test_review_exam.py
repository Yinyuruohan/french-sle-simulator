"""Tests for tools/review_exam.py deterministic checks."""
import pytest


def test_structural_mismatch_fill_in_blank_missing_blank():
    """Flags fill-in-blank context where passage blank numbering doesn't match question_ids."""
    from tools.review_exam import _check_structural_mismatch

    exam = {"contexts": [{
        "context_id": 1,
        "type": "fill_in_blank",
        "passage": "Text with (1) _______________ only.",
        "questions": [
            {"question_id": 1, "options": {"A": "a", "B": "b", "C": "c", "D": "d"}, "correct_answer": "A"},
            {"question_id": 2, "options": {"A": "a", "B": "b", "C": "c", "D": "d"}, "correct_answer": "B"},
        ],
    }]}

    flags = _check_structural_mismatch(exam)
    assert len(flags) >= 1
    assert flags[0]["category"] == "structural_mismatch"
    assert flags[0]["severity"] == "critical"


def test_structural_mismatch_error_id_segment_mismatch():
    """Flags error-ID context where segment labels don't match option keys."""
    from tools.review_exam import _check_structural_mismatch

    # Passage has (A) and (B) only, but options have A, B, C
    exam = {"contexts": [{
        "context_id": 1,
        "type": "error_identification",
        "passage": "Text **segment (A)** and **segment (B)** only.",
        "questions": [{
            "question_id": 1,
            "options": {"A": "segment", "B": "segment", "C": "missing segment", "D": "Aucun des choix offerts."},
            "correct_answer": "A",
        }],
    }]}

    flags = _check_structural_mismatch(exam)
    assert len(flags) >= 1
    assert flags[0]["category"] == "structural_mismatch"


def test_structural_mismatch_clean_exam():
    """No flags for a well-structured exam."""
    from tools.review_exam import _check_structural_mismatch

    exam = {"contexts": [
        {
            "context_id": 1,
            "type": "fill_in_blank",
            "passage": "Text (1) _______________ and (2) _______________ here.",
            "questions": [
                {"question_id": 1, "options": {"A": "a", "B": "b", "C": "c", "D": "d"}, "correct_answer": "A"},
                {"question_id": 2, "options": {"A": "a", "B": "b", "C": "c", "D": "d"}, "correct_answer": "B"},
            ],
        },
        {
            "context_id": 2,
            "type": "error_identification",
            "passage": "Text **seg (A)** and **seg (B)** and **seg (C)** here.",
            "questions": [{
                "question_id": 3,
                "options": {"A": "seg", "B": "seg", "C": "seg", "D": "Aucun des choix offerts."},
                "correct_answer": "A",
            }],
        },
    ]}

    flags = _check_structural_mismatch(exam)
    assert flags == []
