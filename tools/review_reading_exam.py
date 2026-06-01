"""
Rule-based reviewer for SLE Reading Comprehension exams.

Runs deterministic checks beyond the schema validator in
tools/generate_reading_exam.py. No LLM call.

Returns the same {"flagged_questions": [...]} shape as
tools/review_exam.py:review_exam_quality so the cache-prefill
orchestration in tools/reading_question_bank.py can reuse the
WE pattern.
"""
import re

_SENTENCE_COMPLETION_BLANK = re.compile(r"_{4,}\s*\.\s*$")


def review_reading_exam(exam: dict) -> dict:
    """Deterministically review an RC exam.

    severity ∈ {'critical', 'warning'}.
    Critical findings exclude the context from caching in prefill_bank.
    Warning findings cause the context to be cached with status='warned'.
    No retry — matches WE prefill_bank behavior.
    """
    flagged: list[dict] = []
    contexts = exam.get("contexts", [])

    for ctx in contexts:
        flagged.extend(_check_context_critical(ctx))

    return {"flagged_questions": flagged}


def _check_context_critical(ctx: dict) -> list[dict]:
    findings: list[dict] = []
    ctx_id = ctx["context_id"]
    passage = ctx["passage"]
    q = ctx["questions"][0]
    options = q["options"]
    stem_family = q["stem_family"]
    bolded_term = q.get("bolded_term")
    question_text = q.get("question_text", "")

    # duplicate_options — two or more of A/B/C/D have identical text
    values = [options[k].strip().lower() for k in ("A", "B", "C", "D")]
    if len(set(values)) < 4:
        findings.append({
            "context_id": ctx_id,
            "severity": "critical",
            "category": "duplicate_options",
            "issue": f"non-unique options: {values}",
        })

    if stem_family == "vocabulary":
        # bolded_term_missing_in_passage — **bolded_term** absent from passage
        if bolded_term and f"**{bolded_term}**" not in passage:
            findings.append({
                "context_id": ctx_id,
                "severity": "critical",
                "category": "bolded_term_missing_in_passage",
                "issue": f"'**{bolded_term}**' not in passage",
            })
        # vocab_term_missing_in_stem — bolded_term not repeated in question_text
        if bolded_term and bolded_term not in question_text:
            findings.append({
                "context_id": ctx_id,
                "severity": "critical",
                "category": "vocab_term_missing_in_stem",
                "issue": f"'{bolded_term}' not in question_text",
            })

    if stem_family == "sentence_completion":
        if not _SENTENCE_COMPLETION_BLANK.search(passage):
            findings.append({
                "context_id": ctx_id,
                "severity": "critical",
                "category": "sentence_completion_missing_blank",
                "issue": "passage does not end with '____.' pattern",
            })

    return findings
