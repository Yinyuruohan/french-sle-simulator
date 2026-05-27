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
