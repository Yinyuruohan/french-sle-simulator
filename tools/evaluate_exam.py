"""
SLE Written Expression Exam Evaluator

Grades user answers against the answer key, generates detailed French grammar
explanations for incorrect answers via DeepSeek API, computes SLE level,
and logs errors to the persistent tracking file.

Works with the contexts→questions structure where each question uses A/B/C/D.
"""

import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime
from openai import OpenAI
from tools.model_config import ModelConfig, load_default_configs

TMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".tmp")
TRACKING_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "user_error_tracking.md")

LEVEL_THRESHOLDS = {
    "C": 0.90,
    "B": 0.70,
    "A": 0.50,
}


def _determine_level(score_pct: float) -> str:
    if score_pct >= LEVEL_THRESHOLDS["C"]:
        return "C"
    elif score_pct >= LEVEL_THRESHOLDS["B"]:
        return "B"
    elif score_pct >= LEVEL_THRESHOLDS["A"]:
        return "A"
    else:
        return "Below A / Sous le niveau A"


def _generate_explanations(incorrect_items: list, model_config: ModelConfig) -> dict:
    """
    Call DeepSeek API to generate structured grammar explanations.

    Returns dict mapping question_id -> dict with keys:
      why_incorrect, why_correct, grammar_rule
    """
    if not incorrect_items:
        return {}

    client = OpenAI(api_key=model_config.api_key, base_url=model_config.base_url)

    is_regeneration = any("previous_explanation" in item for item in incorrect_items)

    questions_text = ""
    for item in incorrect_items:
        q = item["question"]
        opts = q["options"]
        opts_str = " | ".join(f"{k}) {v}" for k, v in opts.items())
        questions_text += f"""
Question ({q['question_id']}) [{q['grammar_topic']}]:
Context passage: {item['passage']}
Options: {opts_str}
Candidate chose: {item['user_answer']}) {opts[item['user_answer']]}
Correct answer: {q['correct_answer']}) {opts[q['correct_answer']]}
"""
        # Include previous explanation and reviewer feedback when regenerating
        prev_expl = item.get("previous_explanation")
        flag = item.get("flagged_issue")
        if prev_expl and flag:
            if isinstance(prev_expl, dict):
                questions_text += f"""
PREVIOUS EXPLANATION (REJECTED BY REVIEWER):
  why_incorrect: {prev_expl.get('why_incorrect', 'N/A')}
  why_correct: {prev_expl.get('why_correct', 'N/A')}
  grammar_rule: {prev_expl.get('grammar_rule', 'N/A')}
REVIEWER FEEDBACK [{flag.get('category', 'unknown')}]: {flag.get('issue', 'N/A')}
YOU MUST write a COMPLETELY DIFFERENT explanation that fixes the reviewer's concern. Do NOT repeat the same reasoning.
"""
            else:
                questions_text += f"""
PREVIOUS EXPLANATION (REJECTED): {prev_expl}
REVIEWER FEEDBACK [{flag.get('category', 'unknown')}]: {flag.get('issue', 'N/A')}
YOU MUST write a COMPLETELY DIFFERENT explanation that fixes the reviewer's concern.
"""
        questions_text += "---\n"

    if is_regeneration:
        intro = """You are a French grammar expert CORRECTING previously rejected explanations for an SLE Written Expression exam.

The previous explanations were flagged by a quality reviewer. You MUST address the reviewer's specific feedback and produce accurate, corrected explanations.

For each question below, provide a structured explanation with THREE separate parts:
1. **why_incorrect**: Why the candidate's chosen answer is wrong (1-2 sentences)
2. **why_correct**: Why the correct answer is right (1-2 sentences)
3. **grammar_rule**: The specific French grammar rule with a brief example (1-2 sentences)

IMPORTANT: Read the reviewer feedback carefully. If the reviewer says the reasoning is wrong, write completely new reasoning. If the reviewer says the grammar rule is incorrect, cite the correct rule. Do NOT repeat the same mistakes."""
    else:
        intro = """You are a French grammar expert providing feedback on an SLE Written Expression exam.

For each incorrect answer below, provide a structured explanation with THREE separate parts:
1. **why_incorrect**: Why the candidate's chosen answer is wrong (1-2 sentences)
2. **why_correct**: Why the correct answer is right (1-2 sentences)
3. **grammar_rule**: The specific French grammar rule with a brief example (1-2 sentences)"""

    prompt = f"""{intro}

Write in English with French examples where helpful. Be precise and educational.

{questions_text}

Return a JSON object mapping question IDs (as strings) to objects:
{{
  "1": {{
    "why_incorrect": "...",
    "why_correct": "...",
    "grammar_rule": "..."
  }}
}}

Return ONLY the JSON object."""

    response = client.chat.completions.create(
        model=model_config.model,
        messages=[
            {"role": "system", "content": "You are a French grammar expert providing exam feedback. Return only valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=4000,
        response_format={"type": "json_object"}
    )

    raw = response.choices[0].message.content.strip()
    explanations_raw = json.loads(raw)

    return {int(k): v for k, v in explanations_raw.items()}


def _append_to_tracking(session_id: str, incorrect_items: list, explanations: dict):
    """Append incorrect answers to the persistent tracking file."""
    if not incorrect_items:
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"\n## Session: {session_id}",
        f"**Date:** {timestamp}",
        f"**Incorrect answers:** {len(incorrect_items)}",
        "",
    ]

    for item in incorrect_items:
        q = item["question"]
        qid = q["question_id"]
        opts = q["options"]
        expl = explanations.get(qid, {})

        lines.append(f"### Question ({qid})")
        lines.append(f"- **Passage:** {item['passage']}")
        lines.append(f"- **Candidate's answer:** {item['user_answer']}) {opts[item['user_answer']]}")
        lines.append(f"- **Correct answer:** {q['correct_answer']}) {opts[q['correct_answer']]}")
        lines.append(f"- **Error category:** {q['grammar_topic']}")
        if isinstance(expl, dict):
            lines.append(f"- **Why incorrect:** {expl.get('why_incorrect', 'N/A')}")
            lines.append(f"- **Why correct:** {expl.get('why_correct', 'N/A')}")
            lines.append(f"- **Grammar rule:** {expl.get('grammar_rule', 'N/A')}")
        else:
            lines.append(f"- **Explanation:** {expl}")
        lines.append("")

    lines.append("---")
    lines.append("")

    if not os.path.exists(TRACKING_FILE):
        header = "# SLE Exam Error Tracking / Suivi des erreurs\n\nThis file logs all incorrect answers across exam sessions for adaptive learning.\n\n---\n"
        with open(TRACKING_FILE, "w", encoding="utf-8") as f:
            f.write(header)

    with open(TRACKING_FILE, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))


def evaluate_exam(exam: dict, user_answers: dict, model_config: ModelConfig = None) -> dict:
    """
    Evaluate user answers against the exam answer key.

    Args:
        exam: The exam dict from generate_exam() with contexts→questions
        user_answers: Dict mapping question_id (int) -> user's letter ("A"/"B"/"C"/"D")

    Returns:
        dict with: session_id, score, total, percentage, level, context_results
    """
    cfg = model_config or load_default_configs()["evaluate"]
    if not cfg.api_key or cfg.api_key == "your_deepseek_key_here":
        raise ValueError("No API key configured. Set DEEPSEEK_API_KEY (or EVALUATE_API_KEY) in .env")

    session_id = exam.get("session_id", f"exam_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

    correct_count = 0
    total_count = 0
    incorrect_items = []
    context_results = []

    for ctx in exam.get("contexts", []):
        ctx_result = {
            "context_id": ctx["context_id"],
            "type": ctx["type"],
            "passage": ctx["passage"],
            "question_results": [],
        }

        for q in ctx.get("questions", []):
            qid = q["question_id"]
            user_ans = user_answers.get(qid, "")
            is_correct = user_ans == q["correct_answer"]
            total_count += 1

            if is_correct:
                correct_count += 1

            q_result = {
                "question_id": qid,
                "grammar_topic": q["grammar_topic"],
                "options": q["options"],
                "user_answer": user_ans,
                "correct_answer": q["correct_answer"],
                "is_correct": is_correct,
                "explanation": None,
            }
            ctx_result["question_results"].append(q_result)

            if not is_correct:
                incorrect_items.append({
                    "question": q,
                    "passage": ctx["passage"],
                    "user_answer": user_ans,
                })

        context_results.append(ctx_result)

    # Generate explanations for incorrect answers
    explanations = _generate_explanations(incorrect_items, cfg)

    # Attach explanations to results
    for ctx_r in context_results:
        for q_r in ctx_r["question_results"]:
            if not q_r["is_correct"]:
                q_r["explanation"] = explanations.get(q_r["question_id"])

    percentage = (correct_count / total_count * 100) if total_count > 0 else 0
    level = _determine_level(percentage / 100)

    evaluation = {
        "session_id": session_id,
        "score": correct_count,
        "total": total_count,
        "percentage": round(percentage, 1),
        "level": level,
        "context_results": context_results,
    }

    _save_feedback_markdown(evaluation)
    _append_to_tracking(session_id, incorrect_items, explanations)

    return evaluation


def _save_feedback_markdown(evaluation: dict):
    """Save evaluation feedback as a clean, readable markdown file in .tmp/"""
    os.makedirs(TMP_DIR, exist_ok=True)

    session_id = evaluation["session_id"]
    feedback_id = session_id.replace("exam_", "feedback_")
    filepath = os.path.join(TMP_DIR, f"{feedback_id}.md")

    lines = [
        "# SLE Exam Results / Résultats de l'examen ELS",
        "",
        f"**Session:** {session_id}",
        f"**Score:** {evaluation['score']} / {evaluation['total']} ({evaluation['percentage']}%)",
        f"**Level / Niveau:** {evaluation['level']}",
        "",
        "> C >= 90% | B >= 70% | A >= 50% | Below A < 50%",
        "> *Unofficial estimate / Estimation non officielle*",
        "",
        "---",
        "",
    ]

    for ctx_r in evaluation["context_results"]:
        ctx_type = "Fill in the blank" if ctx_r["type"] == "fill_in_blank" else "Error identification"
        lines.append(f"## Context {ctx_r['context_id']} — {ctx_type}")
        lines.append("")
        lines.append(ctx_r["passage"])
        lines.append("")

        for q_r in ctx_r["question_results"]:
            status = "CORRECT ✅" if q_r["is_correct"] else "INCORRECT ❌"
            lines.append(f"### Question ({q_r['question_id']}) — {status}")
            lines.append(f"*Grammar topic: {q_r['grammar_topic']}*")
            lines.append("")

            # Options table
            lines.append("| | Option | |")
            lines.append("|---|---|---|")
            opts = q_r["options"]
            for letter in ["A", "B", "C", "D"]:
                opt_text = opts[letter]
                marker = ""
                bold_start = ""
                bold_end = ""

                if letter == q_r["correct_answer"] and letter == q_r["user_answer"]:
                    bold_start = "**"
                    bold_end = "**"
                    marker = "✅ Your answer"
                elif letter == q_r["correct_answer"]:
                    bold_start = "**"
                    bold_end = "**"
                    marker = "← Correct answer"
                elif letter == q_r["user_answer"] and not q_r["is_correct"]:
                    marker = "← Your answer"

                lines.append(f"| {bold_start}{letter}{bold_end} | {bold_start}{opt_text}{bold_end} | {marker} |")

            lines.append("")

            # Explanation for incorrect answers
            expl = q_r.get("explanation")
            if expl and not q_r["is_correct"]:
                if isinstance(expl, dict):
                    lines.append(f"**Why incorrect:** {expl.get('why_incorrect', 'N/A')}")
                    lines.append("")
                    lines.append(f"**Why correct:** {expl.get('why_correct', 'N/A')}")
                    lines.append("")
                    lines.append(f"**Grammar rule:** {expl.get('grammar_rule', 'N/A')}")
                else:
                    lines.append(f"**Explanation:** {expl}")
                lines.append("")

        lines.append("---")
        lines.append("")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return filepath


def regenerate_explanations(incorrect_items: list, model_config: ModelConfig = None) -> dict:
    """
    Re-generate grammar explanations for specific incorrect items.
    Called by the feedback review loop when explanations are flagged as critical.

    Args:
        incorrect_items: list of dicts, each with keys:
            question (dict with question_id, options, correct_answer, grammar_topic),
            passage (str), user_answer (str),
            previous_explanation (dict, optional): the rejected explanation,
            flagged_issue (dict, optional): the reviewer's flag with issue/category

    Returns:
        dict mapping question_id (int) -> explanation dict
    """
    cfg = model_config or load_default_configs()["evaluate"]
    if not cfg.api_key or cfg.api_key == "your_deepseek_key_here":
        raise ValueError("No API key configured. Set DEEPSEEK_API_KEY (or EVALUATE_API_KEY) in .env")
    return _generate_explanations(incorrect_items, cfg)


def resave_feedback_markdown(evaluation: dict):
    """Re-save feedback markdown after explanations have been corrected."""
    return _save_feedback_markdown(evaluation)
