"""Tests for tools/review_reading_exam.py — rule-based reviewer."""
import pytest

from tools.review_reading_exam import review_reading_exam


def _ctx(context_id, passage, *, stem_family="main_idea", options=None,
         correct="A", justification="Reason.", bolded_term=None,
         question_text=None, has_signature=False):
    """Build a one-question RC context dict."""
    return {
        "context_id": context_id,
        "passage": passage,
        "has_signature": has_signature,
        "questions": [{
            "question_id": context_id,
            "stem_family": stem_family,
            "question_text": question_text or "Quelle est l'idée?",
            "options": options or {"A": "alpha", "B": "beta", "C": "gamma", "D": "delta"},
            "correct_answer": correct,
            "justification": justification,
            "bolded_term": bolded_term,
        }],
    }


def _exam(contexts):
    return {"session_id": "test", "num_questions": len(contexts), "contexts": contexts}


def _categories(result, severity=None):
    return [f["category"] for f in result["flagged_questions"]
            if severity is None or f["severity"] == severity]


# --- Critical rules ---

def test_duplicate_options_flagged_critical():
    ctx = _ctx(1, "P" * 100, options={"A": "same", "B": "different", "C": "same", "D": "other"})
    result = review_reading_exam(_exam([ctx, ctx | {"context_id": 2}]))
    crit = [f for f in result["flagged_questions"] if f["severity"] == "critical"]
    assert any(f["category"] == "duplicate_options" and f["context_id"] == 1 for f in crit)


def test_vocabulary_bolded_term_missing_in_passage_flagged_critical():
    ctx = _ctx(
        1,
        "Un texte sans le mot marqué en gras du tout.",
        stem_family="vocabulary",
        bolded_term="désormais",
        question_text="Que signifie le mot souligné (désormais) dans le texte ?",
    )
    result = review_reading_exam(_exam([ctx]))
    cats = _categories(result, severity="critical")
    assert "bolded_term_missing_in_passage" in cats


def test_vocabulary_term_missing_in_stem_flagged_critical():
    ctx = _ctx(
        1,
        "Le mot **désormais** apparaît ici.",
        stem_family="vocabulary",
        bolded_term="désormais",
        question_text="Que signifie le mot souligné dans le texte ?",
    )
    result = review_reading_exam(_exam([ctx]))
    cats = _categories(result, severity="critical")
    assert "vocab_term_missing_in_stem" in cats


def test_sentence_completion_missing_blank_flagged_critical():
    ctx = _ctx(
        1,
        "Une phrase qui ne se termine pas par un blanc.",
        stem_family="sentence_completion",
        question_text="Quel est le groupe de mots qui complète le mieux ce paragraphe ?",
    )
    result = review_reading_exam(_exam([ctx]))
    cats = _categories(result, severity="critical")
    assert "sentence_completion_missing_blank" in cats


def test_clean_critical_only_exam_returns_no_critical():
    """Sanity: a well-formed N=1 main_idea exam has no critical flags."""
    passage = " ".join(["mot"] * 100)
    ctx = _ctx(1, passage)
    result = review_reading_exam(_exam([ctx]))
    assert _categories(result, severity="critical") == []
