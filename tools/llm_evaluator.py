"""
LLM Evaluator — calls the LLM judge and parses its rating/critique.
"""

import os
import re

from openai import OpenAI

from tools.model_config import ModelConfig

_JUDGE_PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "LLM_judge_prompt.md"
)


def _read_judge_prompt() -> str:
    with open(_JUDGE_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


_JUDGE_PROMPT: str = _read_judge_prompt()


def _serialize_context(context_data: dict) -> str:
    lines = [
        f"Type: {context_data['type']}",
        f"Grammar topics: {context_data['grammar_topics']}",
        f"\nPassage:\n{context_data['passage']}",
    ]
    for i, q in enumerate(context_data["questions"], 1):
        lines.append(f"\nQuestion {i}:")
        for letter, text in q["options"].items():
            lines.append(f"  {letter}: {text}")
        lines.append(f"Correct answer: {q['correct_answer']}")
        lines.append(f"Grammar topic: {q['grammar_topic']}")
        if "explanation" in q:
            lines.append(f"Why correct: {q['explanation']['why_correct']}")
            lines.append(f"Grammar rule: {q['explanation']['grammar_rule']}")
    return "\n".join(lines)


def _parse_response(text: str) -> dict:
    rating_match = re.search(
        r"\*{0,2}Rating:?\*{0,2}\s*(Good|Bad)\b", text, re.IGNORECASE
    )
    if not rating_match:
        raise ValueError(
            f"Malformed LLM response: no Rating found. Response: {text[:200]!r}"
        )
    rating = rating_match.group(1).capitalize()

    commentary_match = re.search(
        r"\*{0,2}Commentary:?\*{0,2}\s*(.+)", text, re.IGNORECASE | re.DOTALL
    )
    critique = commentary_match.group(1).strip() if commentary_match else ""

    return {"rating": rating, "critique": critique}


def evaluate_context(context_data: dict, model_config: ModelConfig) -> dict:
    """
    Call the LLM judge and return {"rating": "Good"|"Bad", "critique": "..."}.

    Raises ValueError if the LLM response is malformed (no Rating line).
    """
    system_prompt = _JUDGE_PROMPT
    user_message = _serialize_context(context_data)

    client = OpenAI(api_key=model_config.api_key, base_url=model_config.base_url)
    response = client.chat.completions.create(
        model=model_config.model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.1,
        max_tokens=512,
    )

    text = response.choices[0].message.content
    return _parse_response(text)
