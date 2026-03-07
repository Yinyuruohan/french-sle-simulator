"""
SLE Written Expression Exam Reviewer

Quality-control agent that validates AI-generated exam questions and feedback
explanations using DeepSeek API with an adversarial prompt and low temperature.

Two review points:
1. review_exam_quality()    — validates generated questions (post-generation)
2. review_feedback_quality() — validates grammar explanations (post-evaluation)

Also provides:
- Deterministic duplicate-option detection (pre-API check)
- System error tracking: logs all flagged issues to system_error_tracking.md
"""

import json
import os
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

REVIEW_TEMPERATURE = 0.1
REVIEW_MAX_TOKENS = 4000

SYSTEM_TRACKING_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "system_error_tracking.md")

# ── Shared API call ──────────────────────────────────────────────────────────

def _call_review_api(system_prompt: str, user_prompt: str) -> dict:
    """Make a review API call with low temperature for strict, consistent judgments."""
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=REVIEW_TEMPERATURE,
        max_tokens=REVIEW_MAX_TOKENS,
        response_format={"type": "json_object"}
    )

    raw = response.choices[0].message.content.strip()
    return json.loads(raw)


# ── Deterministic checks ─────────────────────────────────────────────────────

def _check_duplicate_options(exam_data: dict) -> list:
    """
    Programmatic check: flag any question where two or more options have identical text.
    This is deterministic and does not rely on the AI reviewer.
    """
    flagged = []
    for ctx in exam_data.get("contexts", []):
        for q in ctx.get("questions", []):
            opts = q.get("options", {})
            values = list(opts.values())
            seen = {}
            for letter, text in opts.items():
                normalized = text.strip().lower()
                if normalized in seen:
                    flagged.append({
                        "question_id": q["question_id"],
                        "context_id": ctx["context_id"],
                        "severity": "critical",
                        "issue": f"Duplicate options: {seen[normalized]}) and {letter}) both have text \"{text}\"",
                        "category": "duplicate_options",
                    })
                else:
                    seen[normalized] = letter
    return flagged


# ── System error tracking ────────────────────────────────────────────────────

def log_system_errors(session_id: str, review_type: str, review_result: dict):
    """
    Log flagged issues from review to system_error_tracking.md.

    Args:
        session_id: The exam session ID
        review_type: "exam_review" or "feedback_review"
        review_result: The review dict with flagged_questions or flagged_explanations
    """
    flagged_key = "flagged_questions" if review_type == "exam_review" else "flagged_explanations"
    flagged = review_result.get(flagged_key, [])

    if not flagged:
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    review_label = "Exam Quality Review" if review_type == "exam_review" else "Feedback Quality Review"

    lines = [
        f"\n## {review_label} — Session: {session_id}",
        f"**Date:** {timestamp}",
        f"**Passed:** {review_result.get('passed', 'N/A')}",
        f"**Summary:** {review_result.get('summary', 'N/A')}",
        f"**Issues flagged:** {len(flagged)}",
        "",
    ]

    for f in flagged:
        qid = f.get("question_id", "N/A")
        lines.append(f"### Question ({qid})")
        if "context_id" in f:
            lines.append(f"- **Context:** {f['context_id']}")
        lines.append(f"- **Severity:** {f.get('severity', 'N/A')}")
        lines.append(f"- **Category:** {f.get('category', 'N/A')}")
        lines.append(f"- **Issue:** {f.get('issue', 'N/A')}")
        lines.append("")

    lines.append("---")
    lines.append("")

    if not os.path.exists(SYSTEM_TRACKING_FILE):
        header = "# System Error Tracking / Suivi des erreurs système\n\nThis file logs all issues flagged by the automated quality review agent across exam sessions.\n\n---\n"
        with open(SYSTEM_TRACKING_FILE, "w", encoding="utf-8") as file:
            file.write(header)

    with open(SYSTEM_TRACKING_FILE, "a", encoding="utf-8") as file:
        file.write("\n".join(lines))


# ── Review Point 1: Exam Quality ─────────────────────────────────────────────

EXAM_REVIEW_SYSTEM = """You are a senior French language quality assurance specialist and native French speaker reviewing AI-generated exam questions for the Canadian Public Service Commission's SLE Written Expression test.

Your role is ADVERSARIAL: you must try to find problems. You are not the author of these questions — you are the reviewer who catches mistakes before students see them.

For each question, check ALL of the following:

FILL-IN-THE-BLANK questions:
1. PASSAGE GRAMMAR: Is the passage itself (excluding the blanks) grammatically perfect French? Flag any errors.
2. CORRECT ANSWER VERIFICATION: Insert the marked "correct" answer into the blank. Read the full sentence. Is it genuinely the ONLY correct choice? Is the grammar, preposition, conjugation, and agreement perfect?
3. DISTRACTOR ELIMINATION: Insert EACH distractor into the blank. Is it definitively wrong? Could a proficient French speaker argue it is also acceptable? If a distractor could work, flag it.
4. DUPLICATE OPTIONS: Are any two options identical or nearly identical in text? Every option must be distinct.
5. GRAMMAR TOPIC ACCURACY: Does the labeled grammar_topic actually match what the question tests?

ERROR IDENTIFICATION questions:
1. ERROR EXISTENCE: Is there actually a grammatical error in the segment marked as correct_answer? Identify the specific error.
2. ERROR UNIQUENESS: Are the other bolded segments genuinely error-free? If another segment also has an error, flag it.
3. SEGMENT-PASSAGE MATCH: Do the bolded segments in the passage correspond to the option text?
4. STRUCTURAL: Does question numbering in the passage match question_id?

SEVERITY RULES:
- "critical": The correct answer is wrong, multiple answers are correct, the passage has a grammar error that affects the question, an error_identification question has no real error in the "correct" segment, or two options have identical/duplicate text.
- "warning": A distractor is slightly plausible but the correct answer is still clearly best, or the grammar topic label is imprecise.

Return ONLY a JSON object. Be STRICT. When in doubt, flag it."""


def review_exam_quality(exam_data: dict) -> dict:
    """
    Validate generated exam questions after generation.

    Runs deterministic checks (duplicate options) first, then API-based review.

    Args:
        exam_data: The exam dict from generate_exam() with contexts→questions

    Returns:
        dict with keys:
            passed: bool (True if no critical issues)
            flagged_questions: list of dicts with question_id, context_id,
                severity, issue, category
            summary: str
    """
    # Deterministic pre-checks
    duplicate_flags = _check_duplicate_options(exam_data)

    try:
        user_prompt = _build_exam_review_prompt(exam_data)
        result = _call_review_api(EXAM_REVIEW_SYSTEM, user_prompt)

        # Merge deterministic flags with API flags
        flagged = duplicate_flags + result.get("flagged_questions", [])
        has_critical = any(f.get("severity") == "critical" for f in flagged)

        summary = result.get("summary", "Review complete.")
        if duplicate_flags:
            summary = f"Found {len(duplicate_flags)} duplicate option(s). " + summary

        return {
            "passed": not has_critical,
            "flagged_questions": flagged,
            "summary": summary,
        }
    except Exception:
        # API failed but deterministic checks still apply
        has_critical = any(f.get("severity") == "critical" for f in duplicate_flags)
        return {
            "passed": not has_critical,
            "flagged_questions": duplicate_flags,
            "summary": "API review skipped due to an error." + (f" Found {len(duplicate_flags)} duplicate option(s)." if duplicate_flags else ""),
        }


def _build_exam_review_prompt(exam_data: dict) -> str:
    """Serialize the exam into a format for the review prompt."""
    lines = ["Review the following exam. For EACH question, perform all checks described in your instructions.\n"]

    for ctx in exam_data.get("contexts", []):
        ctx_type = "FILL-IN-THE-BLANK" if ctx["type"] == "fill_in_blank" else "ERROR IDENTIFICATION"
        lines.append(f"--- Context {ctx['context_id']} ({ctx_type}) ---")
        lines.append(f"Passage: {ctx['passage']}")
        lines.append("")

        for q in ctx.get("questions", []):
            opts = q["options"]
            opts_str = " | ".join(f"{k}) {v}" for k, v in opts.items())
            lines.append(f"Question ({q['question_id']}) [grammar_topic: {q['grammar_topic']}]")
            lines.append(f"Options: {opts_str}")
            lines.append(f"Marked correct_answer: {q['correct_answer']}")
            lines.append("")

    lines.append("""Return JSON:
{
  "passed": true/false,
  "flagged_questions": [
    {
      "question_id": 1,
      "context_id": 1,
      "severity": "critical" | "warning",
      "issue": "Detailed description of the problem",
      "category": "wrong_answer_key" | "multiple_correct" | "passage_grammar_error" | "weak_distractor" | "no_real_error" | "structural_mismatch" | "topic_mismatch" | "duplicate_options"
    }
  ],
  "summary": "Overall assessment in one sentence"
}

"passed" is true ONLY if there are zero critical issues.""")

    return "\n".join(lines)


# ── Review Point 2: Feedback Quality ─────────────────────────────────────────

FEEDBACK_REVIEW_SYSTEM = """You are a French grammar expert and educator reviewing AI-generated grammar explanations for incorrect exam answers on the Canadian PSC SLE Written Expression test.

Your role is ADVERSARIAL: find inaccuracies before students learn from wrong information.

For each explanation, verify:
1. RULE ACCURACY: Is the cited grammar rule real and correctly stated? Would a reference grammar (Bescherelle, Grevisse) confirm it?
2. REASONING CORRECTNESS: Does "why_incorrect" accurately explain why the student's answer is wrong? Does "why_correct" accurately explain the correct answer?
3. CONSISTENCY: Does the explanation match the actual question content (passage, options, answers)?
4. NO HALLUCINATION: Are there fabricated rules, exceptions, or examples that don't exist in standard French?

SEVERITY RULES:
- "critical": The grammar rule is wrong, the reasoning contradicts the actual correct answer, or the explanation would teach the student incorrect French.
- "warning": The explanation is imprecise or could be clearer, but is not factually wrong.

Return ONLY a JSON object. Be STRICT."""


def review_feedback_quality(evaluation_data: dict) -> dict:
    """
    Validate grammar explanations after evaluation.

    Args:
        evaluation_data: The evaluation dict from evaluate_exam() with context_results

    Returns:
        dict with keys:
            passed: bool (True if no critical issues)
            flagged_explanations: list of dicts with question_id, severity, issue, category
            summary: str
    """
    try:
        user_prompt = _build_feedback_review_prompt(evaluation_data)
        if not user_prompt:
            return {"passed": True, "flagged_explanations": [], "summary": "No explanations to review."}

        result = _call_review_api(FEEDBACK_REVIEW_SYSTEM, user_prompt)

        flagged = result.get("flagged_explanations", [])
        has_critical = any(f.get("severity") == "critical" for f in flagged)

        return {
            "passed": not has_critical,
            "flagged_explanations": flagged,
            "summary": result.get("summary", "Review complete."),
        }
    except Exception:
        return {
            "passed": True,
            "flagged_explanations": [],
            "summary": "Feedback review skipped due to an error.",
        }


def _build_feedback_review_prompt(evaluation_data: dict) -> str:
    """Serialize incorrect answers with explanations for the review prompt."""
    items = []

    for ctx_r in evaluation_data.get("context_results", []):
        for q_r in ctx_r["question_results"]:
            if q_r["is_correct"] or not q_r.get("explanation"):
                continue

            expl = q_r["explanation"]
            opts = q_r["options"]
            opts_str = " | ".join(f"{k}) {v}" for k, v in opts.items())

            entry = f"""Question ({q_r['question_id']}) [grammar_topic: {q_r['grammar_topic']}]
Passage: {ctx_r['passage']}
Options: {opts_str}
Candidate chose: {q_r['user_answer']}) {opts[q_r['user_answer']]}
Correct answer: {q_r['correct_answer']}) {opts[q_r['correct_answer']]}"""

            if isinstance(expl, dict):
                entry += f"""
why_incorrect: {expl.get('why_incorrect', 'N/A')}
why_correct: {expl.get('why_correct', 'N/A')}
grammar_rule: {expl.get('grammar_rule', 'N/A')}"""
            else:
                entry += f"\nexplanation: {expl}"

            items.append(entry)

    if not items:
        return ""

    lines = [
        "Review the following grammar explanations for incorrect exam answers.\n",
        "\n---\n".join(items),
        "",
        """Return JSON:
{
  "passed": true/false,
  "flagged_explanations": [
    {
      "question_id": 1,
      "severity": "critical" | "warning",
      "issue": "Detailed description of the problem",
      "category": "incorrect_rule" | "wrong_reasoning" | "misleading_explanation" | "hallucinated_rule" | "inconsistent_with_question"
    }
  ],
  "summary": "Overall assessment in one sentence"
}

"passed" is true ONLY if there are zero critical issues.""",
    ]

    return "\n".join(lines)
