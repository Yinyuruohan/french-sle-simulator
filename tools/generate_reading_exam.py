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
    "detail_comprehension",
    "intent_purpose",
    "faux_fausse",
    "main_idea",
    "vocabulary",
    "best_title",
    "sentence_completion",
    "source_identification",
    "inference",
    "vraie_not_purpose",
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

Generate mock exams in formal French, modeled on the official Public Service Commission test.
Maintain a neutral examiner tone. The register is general formal French, not narrowly bureaucratic —
many passages have a public-service or institutional tone, but the SLE exam covers home maintenance,
recycling, emergencies, public policy, training, HR, and civic topics with equal weight.

EXAM RULES
- Exactly N passages, one multiple-choice question per passage (4 options A/B/C/D, one correct).
- Passage length: 50–130 words, most in the 55–95 range. Occasionally (for brief notices or
  instructional snippets) a very short passage of 15–40 words is fine. Usually one paragraph.
- Genre is broad: home maintenance tips, recycling and environment briefs, emergency preparedness
  notices, training invitations, conference announcements, job postings, internal memos, ministerial
  declarations, letters of resignation, customer-service messages, public-policy excerpts, descriptive
  paragraphs about buildings or programs.
- Inclusive writing when relevant: employé(e)s, candidat(e)s, gestionnaires, résident(e)s,
  professionnel(le)s, le ou la, son ou sa, Canadiens et Canadiennes.
- Register markers to draw from when the genre fits: à savoir, désormais, néanmoins, cependant,
  en effet, puisque, afin que, bien que, ladite, lesdits, à cet effet, en la matière, sans délai.
- Signature lines are RARE — include one (italicized on its own line, e.g.
  *Le ministre des Affaires sociales et de la famille*) only occasionally, at most about 1 passage in 20,
  and only when the genre naturally calls for it. Do NOT force them. Set has_signature=true only for
  such a passage; otherwise has_signature=false.

STEM-OPTION GRAMMATICAL RELATIONSHIP — CRITICAL
The most distinctive feature of SLE Reading items is how the stem and its four options relate
grammatically. Decide the stem ending FIRST, then style all four options to match it.
- Pattern 1 — colon-ending stem (≈⅔ of items). The stem ends in ":" and the options grammatically
  complete the sentence. Options start lowercase and frequently end with a period. All four share the
  same construction (e.g. all infinitive phrases starting with de/d', or all third-person verb phrases).
  Example stem: "Selon cette nouvelle, l'isolant de vermiculite:" → options like "ne devrait pas être déplacé."
- Pattern 2 — question-mark stem (≈¼ of items). The stem ends in "?" and the options are standalone
  sentences or noun phrases starting with a capital letter.
  Example stem: "Lequel des titres suivants convient le mieux au texte ?" → noun-phrase options.
- The remaining ≈10% use a comma-ending stem, or a colon followed by capitalized noun phrases.
MIX Pattern 1 and Pattern 2 across the exam — both must appear when N allows.
PARALLEL STRUCTURE is mandatory: within a single question, all four options use the same grammatical
form and roughly comparable length. Mixing infinitive phrases with full clauses in one question is a tell.

STEM FAMILIES (use each value verbatim in the stem_family field). The repertoire is flexible, not a
fixed quota — the percentages are realistic frequencies, not requirements. Vary stems freely; for N ≥ 6
try not to repeat the exact same stem wording.
- detail_comprehension (most common, ≈40%) — passage-tailored stem testing whether the reader picked up
  a specific fact, claim, or implication. e.g. "Selon ce texte:" / "D'après ce texte:" /
  "L'auteur(e) suggère:" / "Selon cette note de service, le ou la destinataire …"
- intent_purpose (≈13%) — "Le but du message ci-dessus est :" / "Ce message est une invitation à :" /
  "La présente note a pour objet :" / "L'auteur(e) de cette lettre désire :"
- faux_fausse (≈11%) — "Laquelle des affirmations suivantes est FAUSSE :" / "Lequel des énoncés suivants est FAUX ?"
- main_idea (≈9%) — "Quelle est l'idée qui résume le mieux le sens du texte ?" / "Ce texte parle :" / "Que nous apprend ce texte ?"
- vocabulary (≈7%) — "Que signifie le mot souligné (X) dans le texte ?" / "Quel est le synonyme de l'expression soulignée (X) ?"
  The target expression MUST be bolded in the passage with **markdown** and repeated in parentheses in the stem.
- best_title (≈4%) — "Quel titre convient le mieux au texte ?" / "Quel titre conviendrait le mieux au paragraphe ci-dessus :"
- sentence_completion (≈3%) — passage ends with `___________________________________________.` on its own line,
  stem: "Quel groupe de mots complète le mieux ce paragraphe ?" / "Quelle phrase convient le mieux pour compléter le texte ?"
- source_identification (≈3%) — "Ce texte est un extrait d'un …" / "Ce texte écrit en YYYY est un extrait :"
- inference (≈2%) — "En lisant la description …, on peut en déduire que …" / "De ce paragraphe, nous pouvons conclure que …"
- vraie_not_purpose (rare) — "Laquelle des affirmations suivantes est VRAIE :" / "Laquelle des affirmations suivantes n'est PAS le but de … :"

VARY families across the N items. For N ≥ 6, no single family should appear more than ~1/3 of the time.
For N ≤ 3, favour detail_comprehension, faux_fausse, intent_purpose, main_idea.

DISTRACTOR DESIGN
Each wrong option follows one of:
- Inversion — negates or reverses a fact in the passage.
- Overgeneralization — uses absolute words (tout, seulement, uniquement, jamais, exclusivement) the passage doesn't support.
- Plausible-but-absent — sounds reasonable but isn't in the passage.
- Lexical lure (vocabulary stems only) — a semantic neighbour, a phonetic/visual lookalike, or an unrelated formal word.

For résumé/main_idea and best_title stems, distractors are TRUE peripheral details (or too-narrow / twisted
versions of the topic), not false statements — the correct answer captures the dominant thread.
For faux_fausse stems, three options must be clearly supported and only the correct one contradicts the passage.
Keep all four options roughly comparable in length.

ANSWER KEY BALANCE
Spread correct answers across A/B/C/D. The official exams slightly under-represent A (~17%) and slightly
over-represent B and C (~30% each), so a small bias toward B/C is realistic. For small N, use at least two
different letters. Never cluster on one letter.

JUSTIFICATION
Provide a one-sentence justification for each question, grounded in the passage. Include both correct and 
incorrect items (review is part of learning). Do NOT reference option letters in justifications (since options may be re-rendered).

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
