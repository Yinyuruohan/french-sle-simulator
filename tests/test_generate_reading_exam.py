"""Tests for tools/generate_reading_exam.py — schema validation + ModelConfig wiring."""
import json
import pytest
from unittest.mock import patch, MagicMock
from tools.model_config import ModelConfig


def _valid_exam_json(num=2):
    """Helper: a syntactically valid RC exam JSON string."""
    contexts = []
    for i in range(num):
        contexts.append({
            "context_id": i + 1,
            "passage": f"Passage {i+1}.",
            "topic": f"Sujet distinct {i+1}",
            "has_signature": False,
            "questions": [{
                "question_id": i + 1,
                "stem_family": "main_idea",
                "question_text": "Q?",
                "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
                "correct_answer": "A",
                "justification": "r",
                "bolded_term": None,
            }],
        })
    return json.dumps({"contexts": contexts})


def test_validate_rejects_wrong_question_count():
    from tools.generate_reading_exam import _validate_exam_schema
    exam = json.loads(_valid_exam_json(num=2))
    with pytest.raises(ValueError, match="question count"):
        _validate_exam_schema(exam, expected_n=3)


def test_validate_rejects_multi_question_context():
    from tools.generate_reading_exam import _validate_exam_schema
    exam = json.loads(_valid_exam_json(num=1))
    # add a second question to ctx 1
    exam["contexts"][0]["questions"].append(exam["contexts"][0]["questions"][0].copy())
    with pytest.raises(ValueError, match="exactly one question"):
        _validate_exam_schema(exam, expected_n=1)


def test_validate_rejects_invalid_stem_family():
    from tools.generate_reading_exam import _validate_exam_schema
    exam = json.loads(_valid_exam_json(num=1))
    exam["contexts"][0]["questions"][0]["stem_family"] = "not_a_family"
    with pytest.raises(ValueError, match="stem_family"):
        _validate_exam_schema(exam, expected_n=1)


def test_validate_rejects_missing_required_field():
    from tools.generate_reading_exam import _validate_exam_schema
    exam = json.loads(_valid_exam_json(num=1))
    del exam["contexts"][0]["questions"][0]["correct_answer"]
    with pytest.raises(ValueError, match="missing"):
        _validate_exam_schema(exam, expected_n=1)


def test_validate_rejects_bolded_term_on_non_vocabulary():
    from tools.generate_reading_exam import _validate_exam_schema
    exam = json.loads(_valid_exam_json(num=1))
    exam["contexts"][0]["questions"][0]["bolded_term"] = "something"
    # stem is main_idea, not vocabulary
    with pytest.raises(ValueError, match="bolded_term"):
        _validate_exam_schema(exam, expected_n=1)


def test_validate_rejects_vocabulary_missing_bolded_term():
    from tools.generate_reading_exam import _validate_exam_schema
    exam = json.loads(_valid_exam_json(num=1))
    exam["contexts"][0]["questions"][0]["stem_family"] = "vocabulary"
    exam["contexts"][0]["questions"][0]["bolded_term"] = None
    with pytest.raises(ValueError, match="bolded_term"):
        _validate_exam_schema(exam, expected_n=1)


def test_validate_accepts_valid_exam():
    from tools.generate_reading_exam import _validate_exam_schema
    exam = json.loads(_valid_exam_json(num=2))
    _validate_exam_schema(exam, expected_n=2)  # should not raise


def test_generate_reading_exam_uses_model_config():
    """generate_reading_exam constructs OpenAI with cfg values and passes model."""
    cfg = ModelConfig(api_key="rk", base_url="https://reading.example.com", model="rmodel")

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = _valid_exam_json(num=3)
    mock_client.chat.completions.create.return_value = mock_response

    with patch("tools.generate_reading_exam.OpenAI", return_value=mock_client) as mock_openai:
        from tools.generate_reading_exam import generate_reading_exam
        generate_reading_exam(3, model_config=cfg)

    mock_openai.assert_called_once_with(api_key="rk", base_url="https://reading.example.com")
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs.get("model") == "rmodel"
    assert call_kwargs.get("max_tokens") == 8000
    assert call_kwargs.get("temperature") == 0.7
    assert call_kwargs.get("response_format") == {"type": "json_object"}


def test_generate_reading_exam_rejects_out_of_range_n():
    from tools.generate_reading_exam import generate_reading_exam
    cfg = ModelConfig(api_key="k", base_url="https://x", model="m")
    with pytest.raises(ValueError, match="2.*30"):
        generate_reading_exam(1, model_config=cfg)
    with pytest.raises(ValueError, match="2.*30"):
        generate_reading_exam(31, model_config=cfg)


def test_generate_reading_exam_rejects_missing_api_key():
    from tools.generate_reading_exam import generate_reading_exam
    cfg = ModelConfig(api_key="", base_url="https://x", model="m")
    with pytest.raises(ValueError, match="No API key"):
        generate_reading_exam(5, model_config=cfg)


def test_generate_reading_exam_returns_validated_exam_with_session_id():
    cfg = ModelConfig(api_key="k", base_url="https://x", model="m")
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = _valid_exam_json(num=2)
    mock_client.chat.completions.create.return_value = mock_response

    with patch("tools.generate_reading_exam.OpenAI", return_value=mock_client):
        from tools.generate_reading_exam import generate_reading_exam
        exam = generate_reading_exam(2, model_config=cfg)

    assert exam["exam_kind"] == "reading_comprehension"
    assert exam["session_id"].startswith("reading_")
    assert len(exam["contexts"]) == 2


def test_generate_reading_exam_raises_on_malformed_json():
    cfg = ModelConfig(api_key="k", base_url="https://x", model="m")
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "not json at all"
    mock_client.chat.completions.create.return_value = mock_response

    with patch("tools.generate_reading_exam.OpenAI", return_value=mock_client):
        from tools.generate_reading_exam import generate_reading_exam
        with pytest.raises(ValueError, match="JSON"):
            generate_reading_exam(2, model_config=cfg)


def test_generate_reading_exam_raises_on_wrong_count():
    cfg = ModelConfig(api_key="k", base_url="https://x", model="m")
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = _valid_exam_json(num=2)
    mock_client.chat.completions.create.return_value = mock_response

    with patch("tools.generate_reading_exam.OpenAI", return_value=mock_client):
        from tools.generate_reading_exam import generate_reading_exam
        with pytest.raises(ValueError, match="question count"):
            generate_reading_exam(5, model_config=cfg)


def test_validate_rejects_missing_topic():
    from tools.generate_reading_exam import _validate_exam_schema
    exam = json.loads(_valid_exam_json(num=1))
    del exam["contexts"][0]["topic"]
    with pytest.raises(ValueError, match="topic"):
        _validate_exam_schema(exam, expected_n=1)


def test_validate_rejects_empty_topic():
    from tools.generate_reading_exam import _validate_exam_schema
    exam = json.loads(_valid_exam_json(num=1))
    exam["contexts"][0]["topic"] = "   "
    with pytest.raises(ValueError, match="topic"):
        _validate_exam_schema(exam, expected_n=1)


def test_generate_reading_exam_passes_avoid_topics_in_user_prompt():
    """avoid_topics are injected into the user prompt as an exclusion list."""
    cfg = ModelConfig(api_key="k", base_url="https://x", model="m")
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = _valid_exam_json(num=2)
    mock_client.chat.completions.create.return_value = mock_response

    with patch("tools.generate_reading_exam.OpenAI", return_value=mock_client):
        from tools.generate_reading_exam import generate_reading_exam
        generate_reading_exam(2, model_config=cfg,
                              avoid_topics=["recyclage municipal", "télétravail"])

    messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
    user_msg = next(m for m in messages if m["role"] == "user")["content"]
    assert "recyclage municipal" in user_msg
    assert "télétravail" in user_msg


def test_generate_reading_exam_omits_avoid_clause_without_topics():
    cfg = ModelConfig(api_key="k", base_url="https://x", model="m")
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = _valid_exam_json(num=2)
    mock_client.chat.completions.create.return_value = mock_response

    with patch("tools.generate_reading_exam.OpenAI", return_value=mock_client):
        from tools.generate_reading_exam import generate_reading_exam
        generate_reading_exam(2, model_config=cfg)

    messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
    user_msg = next(m for m in messages if m["role"] == "user")["content"]
    assert "recently used topics" not in user_msg


def test_prompt_requires_distinct_topics():
    """The system prompt must state the hard topic-diversity rule and the topic field."""
    from tools.generate_reading_exam import SYSTEM_PROMPT
    text = SYSTEM_PROMPT.lower()
    assert '"topic"' in text
    assert "distinct" in text


def test_generate_reading_exam_prompt_mentions_stem_families_and_distractors():
    """Sanity check the system prompt covers required rules."""
    from tools.generate_reading_exam import SYSTEM_PROMPT
    text = SYSTEM_PROMPT.lower()
    assert "stem_family" in text or "stem family" in text
    assert "distractor" in text or "distracteur" in text
    assert "signature" in text  # signature-line rule
    assert "justification" in text
