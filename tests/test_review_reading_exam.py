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


# --- Warning rules (per-context) ---

def test_word_count_under_80_flagged_warning():
    short_passage = "Texte trop court."  # 3 words
    ctx = _ctx(1, short_passage)
    result = review_reading_exam(_exam([ctx]))
    cats = _categories(result, severity="warning")
    assert "word_count_out_of_range" in cats


def test_word_count_over_130_flagged_warning():
    long_passage = " ".join(["mot"] * 140)
    ctx = _ctx(1, long_passage)
    result = review_reading_exam(_exam([ctx]))
    cats = _categories(result, severity="warning")
    assert "word_count_out_of_range" in cats


def test_word_count_in_range_not_flagged():
    ok_passage = " ".join(["mot"] * 100)
    ctx = _ctx(1, ok_passage)
    result = review_reading_exam(_exam([ctx]))
    cats = _categories(result, severity="warning")
    assert "word_count_out_of_range" not in cats


def test_option_length_disparity_flagged_warning():
    options = {"A": "x", "B": "yy", "C": "z" * 50, "D": "ww"}  # longest 50 > 3*1
    ctx = _ctx(1, " ".join(["mot"] * 100), options=options)
    result = review_reading_exam(_exam([ctx]))
    cats = _categories(result, severity="warning")
    assert "option_length_disparity" in cats


# --- Warning rules (N-level) — attached to every surviving context ---

def test_signature_missing_for_n5_flagged_on_all_contexts():
    """N=5, no has_signature=True → every context gets the warning."""
    passage = " ".join(["mot"] * 100)
    contexts = [_ctx(i + 1, passage, has_signature=False) for i in range(5)]
    result = review_reading_exam(_exam(contexts))
    sig_ctx_ids = sorted({f["context_id"] for f in result["flagged_questions"]
                          if f["category"] == "signature_missing"})
    assert sig_ctx_ids == [1, 2, 3, 4, 5]


def test_signature_present_for_n5_not_flagged():
    passage = " ".join(["mot"] * 100)
    contexts = [_ctx(i + 1, passage, has_signature=(i == 0)) for i in range(5)]
    result = review_reading_exam(_exam(contexts))
    assert "signature_missing" not in _categories(result)


def test_signature_missing_for_n_lt_5_not_flagged():
    passage = " ".join(["mot"] * 100)
    contexts = [_ctx(i + 1, passage) for i in range(4)]
    result = review_reading_exam(_exam(contexts))
    assert "signature_missing" not in _categories(result)


def test_answer_key_clustering_over_70pct_flagged():
    """N=5, 4/5 = 80% same letter → flagged on every context."""
    passage = " ".join(["mot"] * 100)
    contexts = [_ctx(i + 1, passage, correct="A") for i in range(4)]
    contexts.append(_ctx(5, passage, correct="B"))
    result = review_reading_exam(_exam(contexts))
    clust = [f["context_id"] for f in result["flagged_questions"]
             if f["category"] == "answer_key_clustering"]
    assert sorted(clust) == [1, 2, 3, 4, 5]


def test_answer_key_clustering_below_70pct_not_flagged():
    passage = " ".join(["mot"] * 100)
    letters = ["A", "B", "A", "C", "B"]
    contexts = [_ctx(i + 1, passage, correct=l) for i, l in enumerate(letters)]
    result = review_reading_exam(_exam(contexts))
    assert "answer_key_clustering" not in _categories(result)


def test_stem_family_overuse_for_n6_flagged():
    """N=6, ceil(6/3)=2, so 3 same family triggers the warning."""
    passage = " ".join(["mot"] * 100)
    families = ["main_idea"] * 3 + ["title", "purpose", "genre"]
    contexts = [_ctx(i + 1, passage, stem_family=f) for i, f in enumerate(families)]
    result = review_reading_exam(_exam(contexts))
    overuse = [f["context_id"] for f in result["flagged_questions"]
               if f["category"] == "stem_family_overuse"]
    assert sorted(overuse) == [1, 2, 3, 4, 5, 6]


def test_stem_family_overuse_at_threshold_not_flagged():
    """N=6, 2 same family is at ceil(6/3) = 2 → NOT > 2 → no flag."""
    passage = " ".join(["mot"] * 100)
    families = ["main_idea", "main_idea", "title", "purpose", "genre", "vocabulary"]
    contexts = []
    for i, f in enumerate(families):
        if f == "vocabulary":
            ctx = _ctx(
                i + 1, passage + " Le mot **désormais** ici.",
                stem_family="vocabulary", bolded_term="désormais",
                question_text="Que signifie (désormais) ?",
            )
        else:
            ctx = _ctx(i + 1, passage, stem_family=f)
        contexts.append(ctx)
    result = review_reading_exam(_exam(contexts))
    assert "stem_family_overuse" not in _categories(result)
