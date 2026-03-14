"""Tests for ModelConfig wiring in tools/generate_exam.py"""
import pytest
from unittest.mock import patch, MagicMock
from tools.model_config import ModelConfig


def test_generate_exam_uses_model_config_model(monkeypatch):
    """generate_exam passes cfg.model to the OpenAI API call."""
    cfg = ModelConfig(api_key="test-key", base_url="https://test.example.com", model="test-model")

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = (
        '{"contexts": [{"context_id": 1, "type": "fill_in_blank", "passage": "Test (1) ___.", '
        '"questions": [{"question_id": 1, "options": {"A": "a", "B": "b", "C": "c", "D": "d"}, '
        '"correct_answer": "A", "grammar_topic": "test"}]}]}'
    )
    mock_client.chat.completions.create.return_value = mock_response

    with patch("tools.generate_exam.OpenAI", return_value=mock_client) as mock_openai:
        from tools.generate_exam import generate_exam
        generate_exam(5, model_config=cfg)

    # Verify OpenAI was constructed with the config values
    mock_openai.assert_called_once_with(api_key="test-key", base_url="https://test.example.com")
    # Verify the model name was passed to the API call
    call_kwargs = mock_client.chat.completions.create.call_args
    assert call_kwargs.kwargs.get("model") == "test-model" or call_kwargs[1].get("model") == "test-model"


def test_generate_exam_raises_on_missing_api_key():
    """generate_exam raises ValueError when api_key is empty."""
    cfg = ModelConfig(api_key="", base_url="https://test.example.com", model="m")
    from tools.generate_exam import generate_exam
    with pytest.raises(ValueError, match="No API key"):
        generate_exam(5, model_config=cfg)


def test_regenerate_context_uses_model_config(monkeypatch):
    """regenerate_context passes cfg.model to the OpenAI API call."""
    cfg = ModelConfig(api_key="regen-key", base_url="https://regen.example.com", model="regen-model")

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = (
        '{"context_id": 1, "type": "fill_in_blank", "passage": "Test (1) ___.", '
        '"questions": [{"question_id": 1, "options": {"A": "a", "B": "b", "C": "c", "D": "d"}, '
        '"correct_answer": "A", "grammar_topic": "test"}]}'
    )
    mock_client.chat.completions.create.return_value = mock_response

    ctx = {
        "context_id": 1, "type": "fill_in_blank",
        "passage": "Test (1) ___.",
        "questions": [{"question_id": 1, "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
                       "correct_answer": "A", "grammar_topic": "test"}]
    }

    with patch("tools.generate_exam.OpenAI", return_value=mock_client) as mock_openai:
        from tools.generate_exam import regenerate_context
        regenerate_context(ctx, [ctx], 1, [], model_config=cfg)

    mock_openai.assert_called_once_with(api_key="regen-key", base_url="https://regen.example.com")
    call_kwargs = mock_client.chat.completions.create.call_args
    assert call_kwargs.kwargs.get("model") == "regen-model" or call_kwargs[1].get("model") == "regen-model"
