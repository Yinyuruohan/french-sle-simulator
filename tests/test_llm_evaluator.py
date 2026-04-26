# tests/test_llm_evaluator.py
"""Tests for tools/llm_evaluator.py"""
from unittest.mock import MagicMock, patch

import pytest


SAMPLE_CONTEXT = {
    "context_id": "test-123",
    "type": "fill_in_blank",
    "passage": "Le ministère _______________ une nouvelle politique.",
    "questions": [
        {
            "options": {"A": "adopte", "B": "adoptez", "C": "adoptent", "D": "adoptais"},
            "correct_answer": "A",
            "grammar_topic": "conjugation",
            "explanation": {
                "why_correct": "Le sujet est 'Le ministère' (3e personne du singulier).",
                "grammar_rule": "Le verbe s'accorde avec le sujet en personne et en nombre.",
            },
        }
    ],
    "grammar_topics": "conjugation",
    "status": "reviewed",
}


@pytest.fixture
def model_config():
    from tools.model_config import ModelConfig
    return ModelConfig(model="test-model", base_url="https://test.api", api_key="test-key")


@patch("tools.llm_evaluator.OpenAI")
def test_evaluate_context_good(mock_openai, model_config):
    """Returns {"rating": "Good", "critique": "..."} for a Good LLM response."""
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(
            content="**Rating:** Good\n\n**Commentary:** The question correctly tests verb conjugation."
        ))]
    )

    from tools.llm_evaluator import evaluate_context
    result = evaluate_context(SAMPLE_CONTEXT, model_config)

    assert result["rating"] == "Good"
    assert len(result["critique"]) > 0


@patch("tools.llm_evaluator.OpenAI")
def test_evaluate_context_bad(mock_openai, model_config):
    """Returns {"rating": "Bad", "critique": "..."} for a Bad LLM response."""
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(
            content="**Rating:** Bad\n\n**Commentary:** The distractor 'adoptez' is implausible."
        ))]
    )

    from tools.llm_evaluator import evaluate_context
    result = evaluate_context(SAMPLE_CONTEXT, model_config)

    assert result["rating"] == "Bad"
    assert len(result["critique"]) > 0


@patch("tools.llm_evaluator.OpenAI")
def test_evaluate_context_malformed_raises(mock_openai, model_config):
    """Raises ValueError when LLM response contains no Rating line."""
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="I cannot evaluate this."))]
    )

    from tools.llm_evaluator import evaluate_context
    with pytest.raises(ValueError, match="Malformed LLM response"):
        evaluate_context(SAMPLE_CONTEXT, model_config)


@patch("tools.llm_evaluator.OpenAI")
def test_evaluate_context_passes_judge_prompt_as_system(mock_openai, model_config):
    """System message contains content from LLM_judge_prompt.md."""
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="**Rating:** Good\n\n**Commentary:** OK."))]
    )

    from tools.llm_evaluator import evaluate_context
    evaluate_context(SAMPLE_CONTEXT, model_config)

    call_kwargs = mock_client.chat.completions.create.call_args[1]
    messages = call_kwargs["messages"]
    system_msg = next((m for m in messages if m["role"] == "system"), None)
    assert system_msg is not None
    assert "EVALUATION CRITERIA" in system_msg["content"]
