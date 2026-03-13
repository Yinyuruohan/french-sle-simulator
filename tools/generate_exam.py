"""
SLE Written Expression Exam Generator

Generates French SLE-style multiple-choice exam questions using DeepSeek API
via the OpenAI-compatible SDK. Questions model the official PSC Written Expression
test format: fill-in-the-blank and error identification, set in Canadian federal
workplace scenarios.

Structure: contexts[] → questions[] (each question has its own A/B/C/D choices)
"""

import json
import os
import random
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

TMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".tmp")

# Few-shot examples using the new contexts→questions structure with A/B/C/D
FEW_SHOT_EXAMPLES = """
EXAMPLE (2 fill_in_blank contexts + 1 error_identification context):

{
  "contexts": [
    {
      "context_id": 1,
      "type": "fill_in_blank",
      "passage": "J'aurais besoin (1) _______________ savoir quand vous comptez prendre vos vacances d'été. Je serai absente du 12 au 30 juillet et je dois m'assurer (2) _______________ quelqu'un sur place pour me remplacer.",
      "questions": [
        {
          "question_id": 1,
          "options": {"A": "du", "B": "à", "C": "pour", "D": "de"},
          "correct_answer": "D",
          "grammar_topic": "preposition"
        },
        {
          "question_id": 2,
          "options": {"A": "que ce sera", "B": "qu'elle aura", "C": "qu'il y aura", "D": "que se sera"},
          "correct_answer": "C",
          "grammar_topic": "impersonal_expression"
        }
      ]
    },
    {
      "context_id": 2,
      "type": "fill_in_blank",
      "passage": "C'est avec plaisir que je (3) _______________ fais part du retour de John Kruder à la direction.",
      "questions": [
        {
          "question_id": 3,
          "options": {"A": "leurs", "B": "lui", "C": "vous", "D": "leur"},
          "correct_answer": "C",
          "grammar_topic": "pronoun"
        }
      ]
    },
    {
      "context_id": 3,
      "type": "error_identification",
      "passage": "Tous les employés et employées intéressés par cette mutation doivent me le signaler avant le 15 de ce mois. Si vous **souhaitez poser (A)** votre candidature, veuillez transmettre votre curriculum vitæ **à jour (B)** au service des **resources humaines (C)**.",
      "questions": [
        {
          "question_id": 4,
          "options": {"A": "souhaitez poser", "B": "à jour", "C": "resources humaines", "D": "Aucun des choix offerts."},
          "correct_answer": "C",
          "grammar_topic": "spelling"
        }
      ]
    }
  ]
}

Note how:
- Contexts are numbered 1, 2, 3...
- Questions are numbered CONTINUOUSLY across contexts: (1), (2), (3), (4)...
- Each question has its OWN A/B/C/D options (never combined)
- Fill-in-the-blank contexts have 1 or 2 questions each
- Error identification contexts have exactly 1 question
- For error_identification passages: segments are labeled (A), (B), (C) in the passage; options A/B/C contain the segment text ONLY (no letter label), D is always "Aucun des choix offerts."
"""

SYSTEM_PROMPT = """You are an expert French language test designer for the Canadian federal Public Service Commission (PSC). You create questions for the Second Language Evaluation (SLE) — Test of Written Expression.

You must generate exam content organized as CONTEXTS, each containing one or more QUESTIONS:
- Each context is a workplace passage (email, memo, policy, meeting invitation, announcement)
- Fill-in-the-blank contexts: passage with numbered blanks. Each blank is a separate question with 4 options (A/B/C/D).
- Error identification contexts: passage with 3 bolded segments labeled (A), (B), (C). One question per context. Options A/B/C correspond to the labeled segments; D is always "Aucun des choix offerts."

Grammar areas to test: prepositions, verb conjugation, agreement (gender/number), pronouns, conjunctions, vocabulary, relative pronouns, adverbs, tense usage, passive voice, spelling, syntax.

CRITICAL RULES:
- Every question must have exactly ONE correct answer (A, B, C, or D)
- Distractors must be plausible but clearly wrong to a proficient speaker
- Each question tests a distinct grammar point
- All passages use formal/professional French appropriate for government communications
- For error_identification: the error in the bolded segment must be a real, identifiable grammatical or spelling error. Each bolded segment MUST include its letter label in parentheses at the end: e.g. **segment text (A)**, **segment text (B)**, **segment text (C)**. The options A/B/C MUST contain ONLY the segment text WITHOUT the letter label: e.g. {"A": "segment text", "B": "segment text", "C": "segment text", "D": "Aucun des choix offerts."}
- Question numbering is CONTINUOUS across all contexts (never restart at 1)
- Fill-in-the-blank contexts have 1 or 2 questions (blanks) each
- Error identification contexts have exactly 1 question
- Return ONLY valid JSON, no markdown, no code fences"""


LETTERS = ["A", "B", "C", "D"]


def _shuffle_options(exam_data: dict):
    """
    Randomize the position of options for each question so the correct answer
    isn't predictably in one slot. Modifies exam_data in place.

    Skips error_identification questions entirely — options A/B/C correspond to
    specific bolded passage segments so their order must be preserved, and D is
    always the fixed "Aucun des choix offerts." sentinel.
    """
    for ctx in exam_data.get("contexts", []):
        for q in ctx.get("questions", []):
            # Skip shuffling entirely for error_identification questions.
            # Options A/B/C correspond to specific bolded passage segments, so
            # their order must be preserved. D is always the "Aucun des choix offerts." sentinel.
            if ctx["type"] == "error_identification":
                continue

            opts = q.get("options", {})
            correct_letter = q["correct_answer"]
            correct_text = opts[correct_letter]

            items = list(opts.items())
            random.shuffle(items)
            new_opts = {LETTERS[i]: text for i, (_, text) in enumerate(items)}

            # Update correct_answer to the new position
            for letter, text in new_opts.items():
                if text == correct_text:
                    q["correct_answer"] = letter
                    break

            q["options"] = new_opts



def generate_exam(num_questions: int) -> dict:
    """
    Generate an SLE Written Expression exam with the given number of questions.

    Args:
        num_questions: Total number of individual questions (5-40)

    Returns:
        dict with keys: session_id, contexts, timestamp, num_questions
    """
    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "your_deepseek_key_here":
        raise ValueError("DEEPSEEK_API_KEY not configured in .env")

    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

    num_questions = max(5, min(40, num_questions))
    num_fill_blank = round(num_questions * 0.5)   # 50% fill-in-blank
    num_error_id = num_questions - num_fill_blank

    user_prompt = f"""Generate a French SLE Written Expression exam with exactly {num_questions} total questions:
- {num_fill_blank} fill_in_blank questions (spread across multiple contexts, 1-2 questions per context)
- {num_error_id} error_identification questions (1 question per context)

GRAMMAR COVERAGE REQUIREMENTS:
Cover a broad range of grammar topics across all questions. Do NOT repeat the same grammar_topic more than twice. Distribute questions across these topics, prioritizing those most frequently tested on the real PSC SLE Written Expression exam:
1. agreement (subject-verb, noun-adjective gender/number)
2. conjugation (verb tense, mood, person)
3. preposition
4. vocabulary (word choice, register)
5. tense
6. pronoun / relative_pronoun
7. conjunction
8. spelling
9. syntax
10. adverb
11. passive_voice

Assign a distinct grammar_topic to each question and ensure no topic appears more than twice across all questions.

Here is an example of the exact JSON structure to follow:
{FEW_SHOT_EXAMPLES}

Return a JSON object with this exact structure:
{{
  "contexts": [
    {{
      "context_id": 1,
      "type": "fill_in_blank",
      "passage": "Passage text with (1) _______________ and optionally (2) _______________ for blanks",
      "questions": [
        {{
          "question_id": 1,
          "options": {{"A": "option1", "B": "option2", "C": "option3", "D": "option4"}},
          "correct_answer": "D",
          "grammar_topic": "topic"
        }}
      ]
    }},
    {{
      "context_id": 2,
      "type": "error_identification",
      "passage": "Text with **bolded segment (N)** normal **bolded segment (N+1)** normal **bolded segment (N+2)** rest.",
      "questions": [
        {{
          "question_id": 3,
          "options": {{"A": "segment text", "B": "segment text", "C": "segment text", "D": "Aucun des choix offerts."}},
          "correct_answer": "A",
          "grammar_topic": "topic"
        }}
      ]
    }}
  ]
}}

IMPORTANT RULES:
- question_id must be CONTINUOUS across all contexts: 1, 2, 3, 4... (never restart)
- The blank numbers in the passage text MUST match the question_id values
- correct_answer is a letter: "A", "B", "C", or "D"
- Each question has its OWN set of A/B/C/D options (never combine multiple blanks into one option)
- Fill-in-the-blank contexts: 1 or 2 questions each
- Error identification contexts: exactly 1 question, option D is ALWAYS "Aucun des choix offerts."
- grammar_topic: one of preposition, conjugation, agreement, pronoun, conjunction, vocabulary, relative_pronoun, adverb, tense, passive_voice, spelling, syntax
- Passages must be realistic Canadian federal workplace scenarios
- Return ONLY the JSON object"""

    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7,
        max_tokens=8000,
        response_format={"type": "json_object"}
    )

    raw_content = response.choices[0].message.content.strip()
    exam_data = json.loads(raw_content)

    # Randomize option positions so correct answer isn't always A
    _shuffle_options(exam_data)

    # Count total questions
    total_q = sum(len(ctx.get("questions", [])) for ctx in exam_data.get("contexts", []))

    # Add metadata
    timestamp = datetime.now()
    session_id = f"exam_{timestamp.strftime('%Y%m%d_%H%M%S')}"
    exam_data["session_id"] = session_id
    exam_data["timestamp"] = timestamp.isoformat()
    exam_data["num_questions"] = total_q

    _save_exam_markdown(exam_data)

    return exam_data


def _save_exam_markdown(exam_data: dict):
    """Save the generated exam as a markdown file in .tmp/"""
    os.makedirs(TMP_DIR, exist_ok=True)

    session_id = exam_data["session_id"]
    filepath = os.path.join(TMP_DIR, f"{session_id}.md")

    lines = [
        "# SLE Written Expression Exam / Examen d'expression écrite ELS",
        f"**Session:** {session_id}",
        f"**Date:** {exam_data['timestamp']}",
        f"**Questions:** {exam_data['num_questions']}",
        "",
        "---",
        "",
    ]

    for ctx in exam_data.get("contexts", []):
        ctx_type = "Fill in the blank" if ctx["type"] == "fill_in_blank" else "Error identification"
        lines.append(f"## Context {ctx['context_id']} — {ctx_type}")
        lines.append("")
        lines.append(ctx["passage"])
        lines.append("")

        for q in ctx.get("questions", []):
            lines.append(f"### Question ({q['question_id']})")
            lines.append(f"*Grammar topic: {q['grammar_topic']}*")
            lines.append("")
            opts = q["options"]
            for letter in ["A", "B", "C", "D"]:
                lines.append(f"{letter}) {opts[letter]}")
            lines.append("")

        lines.append("---")
        lines.append("")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return filepath


def resave_exam_markdown(exam_data: dict):
    """Re-save exam markdown after contexts have been regenerated by review."""
    return _save_exam_markdown(exam_data)


def _validate_context(ctx_data: dict, ctx_id: int, ctx_type: str, num_q: int, start_qid: int) -> str | None:
    """
    Validate that a regenerated context has correct structure.
    Returns None if valid, or an error message string if invalid.
    """
    if ctx_data.get("context_id") != ctx_id:
        return f"Wrong context_id: expected {ctx_id}, got {ctx_data.get('context_id')}"
    if ctx_data.get("type") != ctx_type:
        return f"Wrong type: expected {ctx_type}, got {ctx_data.get('type')}"
    if not ctx_data.get("passage"):
        return "Missing passage"

    questions = ctx_data.get("questions", [])
    if len(questions) != num_q:
        return f"Wrong number of questions: expected {num_q}, got {len(questions)}"

    for i, q in enumerate(questions):
        expected_qid = start_qid + i
        if q.get("question_id") != expected_qid:
            return f"Wrong question_id: expected {expected_qid}, got {q.get('question_id')}"
        opts = q.get("options", {})
        if set(opts.keys()) != {"A", "B", "C", "D"}:
            return f"Question {expected_qid}: missing or extra options (got {list(opts.keys())})"
        if q.get("correct_answer") not in {"A", "B", "C", "D"}:
            return f"Question {expected_qid}: invalid correct_answer '{q.get('correct_answer')}'"
        if not q.get("grammar_topic"):
            return f"Question {expected_qid}: missing grammar_topic"
        # Check for duplicate options
        values = [v.strip().lower() for v in opts.values()]
        if len(values) != len(set(values)):
            return f"Question {expected_qid}: duplicate option text detected"

    return None


def regenerate_context(context_to_replace: dict, existing_contexts: list, start_question_id: int, flagged_issues: list = None) -> dict:
    """
    Regenerate a single context that failed quality review.

    Args:
        context_to_replace: The flagged context dict
        existing_contexts: All current contexts (for topic deduplication)
        start_question_id: The question_id to start numbering from
        flagged_issues: List of dicts with question_id, issue, category for each flagged problem

    Returns:
        dict: A replacement context with corrected content

    Raises:
        ValueError: If the regenerated context fails structural validation
    """
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

    ctx_type = context_to_replace["type"]
    num_q = len(context_to_replace.get("questions", []))
    ctx_id = context_to_replace["context_id"]

    # Collect grammar topics already used to avoid duplication
    used_topics = []
    for ctx in existing_contexts:
        if ctx["context_id"] != ctx_id:
            for q in ctx.get("questions", []):
                used_topics.append(q["grammar_topic"])

    type_label = "fill_in_blank" if ctx_type == "fill_in_blank" else "error_identification"
    type_desc = "fill-in-the-blank (passage with numbered blanks)" if ctx_type == "fill_in_blank" else "error identification (passage with 3 bolded segments, option D = 'Aucun des choix offerts.')"

    # Build detailed error section from structured flags
    error_section = ""
    if flagged_issues:
        # Show the original context that failed
        original_passage = context_to_replace.get("passage", "")
        original_questions = ""
        for q in context_to_replace.get("questions", []):
            opts = q["options"]
            opts_str = " | ".join(f"{k}) {v}" for k, v in opts.items())
            original_questions += f"\n  Question ({q['question_id']}): Options: {opts_str}, Marked correct: {q['correct_answer']}, Topic: {q['grammar_topic']}"

        error_lines = [
            "\n=== REJECTED CONTEXT (DO NOT REUSE) ===",
            f"Original passage: {original_passage}",
            f"Original questions: {original_questions}",
            "",
            "SPECIFIC PROBLEMS FOUND BY THE REVIEWER:",
        ]
        for issue in flagged_issues:
            qid = issue.get("question_id", "?")
            cat = issue.get("category", "unknown")
            desc = issue.get("issue", "")
            error_lines.append(f"  - Question ({qid}) [{cat}]: {desc}")

        error_lines.extend([
            "",
            "YOU MUST:",
            "- Write a COMPLETELY DIFFERENT passage (new topic, new scenario)",
            "- Ensure each question has exactly ONE correct answer",
            "- Ensure all distractors are clearly wrong to a proficient French speaker",
            "- Verify the passage grammar is perfect French",
            "- Self-check: insert the correct answer into the blank and confirm the sentence is grammatically perfect",
            "- Self-check: insert each distractor and confirm it creates a grammatical error",
            "=== END OF REJECTED CONTEXT ===",
        ])
        error_section = "\n".join(error_lines)

    prompt = f"""Generate exactly ONE {type_desc} context for a French SLE Written Expression exam.

The context must:
- context_id: {ctx_id}
- type: "{type_label}"
- Contain exactly {num_q} question(s)
- question_id starts at {start_question_id}
- Use A/B/C/D for options
- Be a realistic Canadian federal workplace scenario
- Avoid these grammar topics already covered: {', '.join(used_topics) if used_topics else 'none'}
{error_section}
Return a JSON object with this structure:
{{
  "context_id": {ctx_id},
  "type": "{type_label}",
  "passage": "...",
  "questions": [
    {{
      "question_id": {start_question_id},
      "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
      "correct_answer": "A",
      "grammar_topic": "..."
    }}
  ]
}}

Return ONLY the JSON object."""

    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=2000,
        response_format={"type": "json_object"}
    )

    raw = response.choices[0].message.content.strip()
    ctx_data = json.loads(raw)

    # Structural validation
    validation_error = _validate_context(ctx_data, ctx_id, type_label, num_q, start_question_id)
    if validation_error:
        raise ValueError(f"Regenerated context failed validation: {validation_error}")

    # Randomize option positions for the regenerated context
    _shuffle_options({"contexts": [ctx_data]})

    return ctx_data


if __name__ == "__main__":
    result = generate_exam(5)
    print(json.dumps(result, indent=2, ensure_ascii=False))
