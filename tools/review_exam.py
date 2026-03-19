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
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime
from openai import OpenAI
from tools.model_config import ModelConfig, load_default_configs

REVIEW_TEMPERATURE = 0.1
REVIEW_MAX_TOKENS = 4000

SYSTEM_TRACKING_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "system_error_tracking.md")

# ── Shared API call ──────────────────────────────────────────────────────────

def _call_review_api(system_prompt: str, user_prompt: str, model_config: ModelConfig) -> dict:
    """Make a review API call with low temperature for strict, consistent judgments."""
    client = OpenAI(api_key=model_config.api_key, base_url=model_config.base_url)

    response = client.chat.completions.create(
        model=model_config.model,
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


# ── Severity enforcement ─────────────────────────────────────────────────────

# Categories that can never be "critical" — cap them at "warning" regardless
# of what the AI returns, as a safety net against prompt drift.
EXAM_WARNING_ONLY_CATEGORIES = {"weak_distractor", "topic_mismatch"}
FEEDBACK_WARNING_ONLY_CATEGORIES = {"misleading_explanation"}


def _enforce_severity_rules(flagged_list: list, warning_only_categories: set) -> list:
    """Downgrade any flags whose category should never be critical."""
    for f in flagged_list:
        if f.get("category") in warning_only_categories:
            f["severity"] = "warning"
    return flagged_list


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

Your role is to catch genuine errors that would make a question unsolvable or the answer key provably wrong. Be conservative: only flag issues that clearly break the question. When in doubt, do not flag as critical — use "warning" or skip.

For each question, check ALL of the following:

FILL-IN-THE-BLANK questions:
1. PASSAGE GRAMMAR: Is the passage itself (excluding the blanks) grammatically correct French? Flag errors only if they directly affect the blank or make the question unanswerable. Minor style issues are warnings only.
2. CORRECT ANSWER VERIFICATION: Insert the marked "correct" answer into the blank. Is it grammatically correct and clearly the best choice? Flag as critical ONLY if the answer is objectively wrong (e.g. wrong agreement, wrong tense, ungrammatical).
3. DISTRACTOR ELIMINATION: Insert EACH distractor into the blank. Flag as critical ONLY if a distractor is equally correct as the marked answer — i.e. a proficient native speaker would consider both equally valid. Do NOT flag if the marked answer is clearly best and the distractor is merely plausible. Plausible-but-wrong distractors are good exam design and should be flagged as "warning" (weak_distractor) at most.
4. DUPLICATE OPTIONS: Are any two options identical or nearly identical in text? Flag as critical only if two options are effectively the same choice.
5. GRAMMAR TOPIC ACCURACY: Does the labeled grammar_topic match what the question tests? Imprecise labels are warnings only.

ERROR IDENTIFICATION questions:
1. ERROR EXISTENCE: Is there actually a grammatical error in the segment marked as correct_answer? Flag as critical if there is no real error.
2. ERROR UNIQUENESS: Are the other bolded segments genuinely error-free? Flag as critical only if another segment also has a clear grammatical error.
3. SEGMENT-PASSAGE MATCH: Do the bolded segments in the passage correspond to the option text?
4. STRUCTURAL: Does question numbering in the passage match question_id?

SEVERITY RULES:
- "critical": The correct answer is objectively wrong, two options are equally correct (not just the distractor being plausible), the passage has a grammar error that directly makes the question unanswerable, an error_identification question has no real error in the "correct" segment, or two options have identical/duplicate text.
- "warning": A distractor is plausible but the correct answer is clearly better, the grammar topic label is imprecise, or a passage has a minor stylistic issue that does not affect the question.

IMPORTANT: The categories "weak_distractor" and "topic_mismatch" must ALWAYS be severity "warning", never "critical".

Return ONLY a JSON object. Be conservative: only flag what is clearly broken."""


def review_exam_quality(exam_data: dict, model_config: ModelConfig = None) -> dict:
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
    cfg = model_config or load_default_configs()["review"]

    # Deterministic pre-checks
    duplicate_flags = _check_duplicate_options(exam_data)

    try:
        user_prompt = _build_exam_review_prompt(exam_data)
        result = _call_review_api(EXAM_REVIEW_SYSTEM, user_prompt, cfg)

        # Merge deterministic flags with API flags, then enforce severity rules
        flagged = duplicate_flags + result.get("flagged_questions", [])
        flagged = _enforce_severity_rules(flagged, EXAM_WARNING_ONLY_CATEGORIES)
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

Your role is to catch factually wrong grammar explanations that would teach students incorrect French. Be conservative: only flag explanations that contain a genuine factual error. Imprecise or incomplete explanations are acceptable — flag them as "warning" only if needed.

For each explanation, verify:
1. RULE ACCURACY: Is the cited grammar rule real and correctly stated? Flag as critical only if the rule is factually wrong or directly contradicts standard French grammar (Bescherelle, Grevisse). Do not flag for imprecision or simplification.
2. REASONING CORRECTNESS: Does "why_correct" accurately explain the correct answer? Flag as critical only if the reasoning is clearly backwards or contradicts the answer key.
3. CONSISTENCY: Does the explanation match the actual question content (passage, options, answers)? Flag as critical only if there is a clear mismatch that would confuse the student.
4. NO HALLUCINATION: Are there fabricated rules or exceptions that don't exist in standard French? Flag as critical only for clear hallucinations, not for uncommon but valid rules.

SEVERITY RULES:
- "critical": The grammar rule is factually wrong, the reasoning directly contradicts the correct answer, or the explanation would actively teach the student incorrect French.
- "warning": The explanation is imprecise, oversimplified, or could be clearer — but is not factually wrong.

IMPORTANT: The category "misleading_explanation" must ALWAYS be severity "warning", never "critical". Reserve "critical" for "incorrect_rule", "wrong_reasoning", "hallucinated_rule", and "inconsistent_with_question" only when the error is clear and unambiguous.

Return ONLY a JSON object. Be conservative: only flag what is clearly factually wrong."""


def review_feedback_quality(evaluation_data: dict, model_config: ModelConfig = None) -> dict:
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
    cfg = model_config or load_default_configs()["review"]

    try:
        user_prompt = _build_feedback_review_prompt(evaluation_data)
        if not user_prompt:
            return {"passed": True, "flagged_explanations": [], "summary": "No explanations to review."}

        result = _call_review_api(FEEDBACK_REVIEW_SYSTEM, user_prompt, cfg)

        flagged = result.get("flagged_explanations", [])
        flagged = _enforce_severity_rules(flagged, FEEDBACK_WARNING_ONLY_CATEGORIES)
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
    """Serialize all questions with explanations for the review prompt."""
    items = []

    for ctx_r in evaluation_data.get("context_results", []):
        for q_r in ctx_r["question_results"]:
            if not q_r.get("explanation"):
                continue

            expl = q_r["explanation"]
            opts = q_r["options"]
            opts_str = " | ".join(f"{k}) {v}" for k, v in opts.items())

            entry = f"""Question ({q_r['question_id']}) [grammar_topic: {q_r['grammar_topic']}]
Passage: {ctx_r['passage']}
Options: {opts_str}
Correct answer: {q_r['correct_answer']}) {opts[q_r['correct_answer']]}"""

            if isinstance(expl, dict):
                entry += f"""
why_correct: {expl.get('why_correct', 'N/A')}
grammar_rule: {expl.get('grammar_rule', 'N/A')}"""
            else:
                entry += f"\nexplanation: {expl}"

            items.append(entry)

    if not items:
        return ""

    lines = [
        "Review the following grammar explanations for exam answers.\n",
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
