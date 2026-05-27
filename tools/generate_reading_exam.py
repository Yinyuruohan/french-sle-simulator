"""
SLE Reading Comprehension Exam Generator

Single AI call → JSON exam with N passages, one multiple-choice question per
passage, pre-generated correct answers and justifications.

Reference spec: docs/superpowers/specs/2026-05-26-sle-reading-comprehension-simulator-design.md
Reference prompt source: contexts/sle-reading-comprehension/sle_reading_simulation_prompt.md
"""
import json
import os
import sys
from datetime import datetime
from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.model_config import ModelConfig, load_default_configs

TMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".tmp")

STEM_FAMILIES = [
    "main_idea",
    "false_statement",
    "true_statement",
    "title",
    "purpose",
    "genre",
    "vocabulary",
    "sentence_completion",
    "not_purpose",
    "general_per_text",
]

_REQUIRED_QUESTION_FIELDS = [
    "question_id",
    "stem_family",
    "question_text",
    "options",
    "correct_answer",
    "justification",
    "bolded_term",
]


def _validate_exam_schema(exam: dict, expected_n: int) -> None:
    """Raise ValueError if the exam dict does not match the RC schema."""
    contexts = exam.get("contexts")
    if not isinstance(contexts, list) or len(contexts) != expected_n:
        raise ValueError(
            f"Wrong question count: got {len(contexts) if isinstance(contexts, list) else 'n/a'}, expected {expected_n}"
        )
    for ctx in contexts:
        questions = ctx.get("questions")
        if not isinstance(questions, list) or len(questions) != 1:
            raise ValueError(f"Context {ctx.get('context_id')} must have exactly one question")
        for field in ("context_id", "passage"):
            if field not in ctx:
                raise ValueError(f"Context is missing field '{field}'")
        q = questions[0]
        for f in _REQUIRED_QUESTION_FIELDS:
            if f not in q:
                raise ValueError(f"Question {q.get('question_id')} missing field '{f}'")
        if q["stem_family"] not in STEM_FAMILIES:
            raise ValueError(
                f"Question {q['question_id']} has invalid stem_family '{q['stem_family']}'"
            )
        if q["correct_answer"] not in {"A", "B", "C", "D"}:
            raise ValueError(f"Question {q['question_id']} correct_answer not in A/B/C/D")
        opts = q.get("options")
        if not isinstance(opts, dict) or set(opts.keys()) != {"A", "B", "C", "D"}:
            raise ValueError(f"Question {q['question_id']} options must be a dict with keys A/B/C/D")
        if q["stem_family"] == "vocabulary":
            if not q.get("bolded_term"):
                raise ValueError(
                    f"Question {q['question_id']} is vocabulary but missing bolded_term"
                )
        else:
            if q.get("bolded_term"):
                raise ValueError(
                    f"Question {q['question_id']} has bolded_term but stem_family is not vocabulary"
                )


SYSTEM_PROMPT = """You are a Canadian federal public service SLE Reading Comprehension item-writer.

Generate mock exams in formal administrative French (français de la fonction publique fédérale),
modeled on the official Public Service Commission test. Maintain a neutral examiner tone.

EXAM RULES
- Exactly N passages, one multiple-choice question per passage (4 options A/B/C/D, one correct).
- Each passage: 80–130 words, one paragraph (occasionally two).
- Genres: internal notes, intranet announcements, service messages, policy excerpts, memos, communiqués, ministerial statements, training invitations.
- Inclusive writing throughout: employé(e)s, candidat(e)s, gestionnaires, le ou la, son ou sa.
- Register markers to draw from: à savoir, désormais, néanmoins, cependant, en effet, à en croire, puisque, afin que, bien que, ladite, lesdits, à cet effet, en la matière, en souffrance, sans délai.
- For N >= 5: include at least one passage ending with a signature line on its own line (italicized, e.g. *Le ministre des Affaires sociales et de la famille*) and set has_signature=true for that passage. For N < 5, skip signature lines.

STEM FAMILIES (use each value verbatim in the stem_family field)
- main_idea — "Quelle est l'idée qui résume le mieux le sens du texte ?"
- false_statement — "Lequel des énoncés suivants est FAUX ?" / "Laquelle des affirmations suivantes est FAUSSE ?"
- true_statement — "Laquelle des affirmations suivantes est VRAIE ?"
- title — "Quel titre conviendrait le mieux au texte ci-dessus ?"
- purpose — "Le but du message ci-dessus est :" / "Ce message est une invitation à :"
- genre — "Ce texte est un extrait de / d'un …"
- vocabulary — "Que signifie le mot souligné (…) dans le texte ?" (the target expression MUST be bolded in the passage with **markdown** and repeated in parentheses in the stem)
- sentence_completion — passage ends with `____________________________________________.` on its own line, stem: "Quel est le groupe de mots qui complète le mieux ce paragraphe ?"
- not_purpose — "Laquelle des affirmations suivantes n'est PAS le but de … :"
- general_per_text — "Selon ce texte, …" / "D'après cette déclaration, …" / "Selon cette note de service, …"

VARY families across the N items. For N >= 6, no single family should appear more than ~1/3 of the time. For N <= 3, favour main_idea, false_statement, title, purpose.

DISTRACTOR DESIGN
Each wrong option follows one of:
- Inversion — negates or reverses a fact in the passage.
- Overgeneralization — uses absolute words (tout, seulement, uniquement, jamais, exclusivement) the passage doesn't support.
- Plausible-but-absent — sounds reasonable but isn't in the passage.

For résumé/main_idea stems, distractors are TRUE peripheral details, not false statements.
For false_statement stems, three options must be clearly supported and only the correct one contradicts the passage.
Keep all four options roughly comparable in length.

ANSWER KEY BALANCE
Spread correct answers across A/B/C/D as evenly as N allows. For small N, use at least two different letters. Never cluster.

JUSTIFICATION
Provide a one-sentence justification for each correct answer, grounded in the passage. Do NOT reference option letters in justifications (since options may be re-rendered).

OUTPUT FORMAT — STRICT JSON
{
  "contexts": [
    {
      "context_id": 1,
      "passage": "...",
      "has_signature": false,
      "questions": [
        {
          "question_id": 1,
          "stem_family": "main_idea",
          "question_text": "Quelle est l'idée qui résume le mieux le sens du texte ?",
          "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
          "correct_answer": "B",
          "justification": "...",
          "bolded_term": null
        }
      ]
    }
  ]
}

bolded_term must be a non-empty string only when stem_family == "vocabulary"; otherwise it must be null.
question_id numbering is continuous across passages: 1, 2, 3, ... N.
"""


def generate_reading_exam(num_questions: int, model_config: ModelConfig = None) -> dict:
    """Generate an N-question SLE Reading Comprehension exam.

    Raises ValueError on invalid N, missing API key, malformed JSON, or schema mismatch.
    """
    if not (2 <= num_questions <= 30):
        raise ValueError("num_questions must be between 2 and 30 inclusive")

    if model_config is None:
        model_config = load_default_configs()["reading"]
    if not model_config.api_key:
        raise ValueError("No API key configured for reading-comprehension generator")

    client = OpenAI(api_key=model_config.api_key, base_url=model_config.base_url)

    user_prompt = f"Generate an SLE Reading Comprehension mock exam with N = {num_questions}. Return strict JSON only."

    response = client.chat.completions.create(
        model=model_config.model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=8000,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    try:
        exam = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Model returned invalid JSON: {e}") from e

    _validate_exam_schema(exam, expected_n=num_questions)

    session_id = f"reading_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    exam["session_id"] = session_id
    exam["exam_kind"] = "reading_comprehension"
    exam["num_questions"] = num_questions

    _save_exam_markdown(exam)
    return exam


def _save_exam_markdown(exam: dict) -> None:
    """Write a human-readable copy of the exam under TMP_DIR for record-keeping."""
    os.makedirs(TMP_DIR, exist_ok=True)
    filepath = os.path.join(TMP_DIR, f"{exam['session_id']}.md")
    lines = [
        "# SLE Reading Comprehension Mock Exam",
        "",
        f"**Session:** {exam['session_id']}",
        f"**Questions:** {exam['num_questions']}",
        "",
        "---",
        "",
    ]
    for ctx in exam["contexts"]:
        lines.append(f"## Passage {ctx['context_id']}")
        lines.append("")
        lines.append(f"> {ctx['passage']}")
        lines.append("")
        q = ctx["questions"][0]
        lines.append(f"**Question {q['question_id']}** *({q['stem_family']})*")
        lines.append("")
        lines.append(q["question_text"])
        lines.append("")
        for letter in ["A", "B", "C", "D"]:
            lines.append(f"- **{letter}.** {q['options'][letter]}")
        lines.append("")
        lines.append("---")
        lines.append("")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
