"""
Rule-based reviewer for SLE Reading Comprehension exams.

Runs deterministic checks beyond the schema validator in
tools/generate_reading_exam.py. No LLM call.

Returns the same {"flagged_questions": [...]} shape as
tools/review_exam.py:review_exam_quality so the cache-prefill
orchestration in tools/reading_question_bank.py can reuse the
WE pattern.
"""
import math
import re

_SENTENCE_COMPLETION_BLANK = re.compile(r"_{4,}\s*\.\s*$")


def review_reading_exam(exam: dict) -> dict:
    """Deterministically review an RC exam.

    See module docstring for severity semantics and behavior.
    """
    flagged: list[dict] = []
    contexts = exam.get("contexts", [])
    n = len(contexts)

    surviving_ids: list[int] = []
    for ctx in contexts:
        crit = _check_context_critical(ctx)
        flagged.extend(crit)
        ctx_id = ctx["context_id"]
        if not any(f["context_id"] == ctx_id and f["severity"] == "critical" for f in crit):
            surviving_ids.append(ctx_id)
        flagged.extend(_check_context_warning(ctx))

    flagged.extend(_check_exam_level_warnings(contexts, surviving_ids, n))
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


def _check_context_warning(ctx: dict) -> list[dict]:
    findings: list[dict] = []
    ctx_id = ctx["context_id"]
    passage = ctx["passage"]
    q = ctx["questions"][0]
    options = q["options"]

    word_count = len(passage.split())
    if word_count < 80 or word_count > 130:
        findings.append({
            "context_id": ctx_id,
            "severity": "warning",
            "category": "word_count_out_of_range",
            "issue": f"word count {word_count} (expected 80-130)",
        })

    lengths = [len(options[k].strip()) for k in ("A", "B", "C", "D")]
    shortest = min(lengths)
    longest = max(lengths)
    if shortest >= 1 and longest > 3 * shortest:
        findings.append({
            "context_id": ctx_id,
            "severity": "warning",
            "category": "option_length_disparity",
            "issue": f"option lengths {lengths}",
        })

    return findings


def _check_exam_level_warnings(contexts: list[dict],
                                surviving_ids: list[int],
                                n: int) -> list[dict]:
    """Attach N-level warnings to every surviving context_id."""
    findings: list[dict] = []
    if not surviving_ids:
        return findings

    def _attach(category: str, issue: str):
        for ctx_id in surviving_ids:
            findings.append({
                "context_id": ctx_id,
                "severity": "warning",
                "category": category,
                "issue": issue,
            })

    if n >= 5 and not any(ctx.get("has_signature") for ctx in contexts):
        _attach("signature_missing", f"N={n} with no signature passage")

    if n >= 4:
        letter_counts: dict[str, int] = {}
        for ctx in contexts:
            letter = ctx["questions"][0]["correct_answer"]
            letter_counts[letter] = letter_counts.get(letter, 0) + 1
        max_count = max(letter_counts.values()) if letter_counts else 0
        if max_count / n > 0.70:
            _attach(
                "answer_key_clustering",
                f"max letter count {max_count}/{n} > 70%",
            )

    if n >= 6:
        family_counts: dict[str, int] = {}
        for ctx in contexts:
            fam = ctx["questions"][0]["stem_family"]
            family_counts[fam] = family_counts.get(fam, 0) + 1
        threshold = math.ceil(n / 3)
        over = [fam for fam, c in family_counts.items() if c > threshold]
        if over:
            _attach(
                "stem_family_overuse",
                f"families {over} appear > ceil(N/3)={threshold} times",
            )

    return findings
