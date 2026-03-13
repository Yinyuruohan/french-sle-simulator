# Model Selection Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to configure any OpenAI-compatible model independently for exam generation, evaluation, and review via `.env` defaults and a Streamlit UI expander.

**Architecture:** A new `ModelConfig` dataclass in `tools/model_config.py` is the single source of truth. Each tool function gains a `model_config: ModelConfig = None` parameter — `None` falls back to env-loaded defaults. `app.py` initialises three configs in session state at startup and passes them through all eight tool call sites.

**Tech Stack:** Python 3.10+, `dataclasses`, `python-dotenv`, `openai` SDK, `streamlit`

---

## Chunk 1: `tools/model_config.py` — new module + tests

### Task 1: Create test infrastructure and write failing tests for `ModelConfig`

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_model_config.py`

- [ ] **Step 1: Create the tests directory, empty init, and conftest**

```bash
mkdir tests
touch tests/__init__.py
```

Create `tests/conftest.py` — ensures project root is on sys.path for all tests:

```python
import sys
import os

# Add project root to sys.path so 'from tools.X import ...' works in tests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_model_config.py`:

```python
"""Tests for tools/model_config.py

Note on isolation: load_dotenv() fires at module import time, so patching it
after import is a no-op. monkeypatch.setenv/delenv is sufficient — it directly
controls os.environ, and load_default_configs() reads os.environ at call time,
so monkeypatch values always win regardless of what load_dotenv() did earlier.
"""
import pytest
from tools.model_config import ModelConfig, load_default_configs


def test_modelconfig_stores_fields():
    """ModelConfig holds api_key, base_url, model."""
    cfg = ModelConfig(api_key="k", base_url="https://example.com", model="m")
    assert cfg.api_key == "k"
    assert cfg.base_url == "https://example.com"
    assert cfg.model == "m"


def test_load_default_configs_returns_three_keys(monkeypatch):
    """load_default_configs returns generate, evaluate, review keys."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    configs = load_default_configs()
    assert set(configs.keys()) == {"generate", "evaluate", "review"}


def test_load_default_configs_falls_back_to_deepseek_key(monkeypatch):
    """When per-tool vars are absent, all configs use DEEPSEEK_API_KEY."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-key")
    for k in ["GENERATE_API_KEY", "EVALUATE_API_KEY", "REVIEW_API_KEY",
              "GENERATE_BASE_URL", "EVALUATE_BASE_URL", "REVIEW_BASE_URL",
              "GENERATE_MODEL", "EVALUATE_MODEL", "REVIEW_MODEL"]:
        monkeypatch.delenv(k, raising=False)

    configs = load_default_configs()

    assert configs["generate"].api_key == "ds-key"
    assert configs["evaluate"].api_key == "ds-key"
    assert configs["review"].api_key == "ds-key"


def test_load_default_configs_uses_per_tool_overrides(monkeypatch):
    """Per-tool env vars override the DEEPSEEK fallback."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-key")
    monkeypatch.setenv("GENERATE_API_KEY", "gen-key")
    monkeypatch.setenv("GENERATE_BASE_URL", "https://gen.example.com")
    monkeypatch.setenv("GENERATE_MODEL", "gen-model")
    for k in ["EVALUATE_API_KEY", "EVALUATE_BASE_URL", "EVALUATE_MODEL",
              "REVIEW_API_KEY", "REVIEW_BASE_URL", "REVIEW_MODEL"]:
        monkeypatch.delenv(k, raising=False)

    configs = load_default_configs()

    assert configs["generate"].api_key == "gen-key"
    assert configs["generate"].base_url == "https://gen.example.com"
    assert configs["generate"].model == "gen-model"
    assert configs["evaluate"].api_key == "ds-key"  # falls back to DEEPSEEK


def test_empty_string_per_tool_key_falls_back(monkeypatch):
    """Empty string per-tool env var is treated as absent (falsy → fallback)."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-key")
    monkeypatch.setenv("GENERATE_API_KEY", "")  # empty string is falsy

    configs = load_default_configs()

    assert configs["generate"].api_key == "ds-key"


def test_default_base_url_and_model(monkeypatch):
    """Without overrides, base_url and model default to DeepSeek values."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k")
    for k in ["GENERATE_BASE_URL", "GENERATE_MODEL"]:
        monkeypatch.delenv(k, raising=False)

    configs = load_default_configs()

    assert configs["generate"].base_url == "https://api.deepseek.com"
    assert configs["generate"].model == "deepseek-chat"
```

- [ ] **Step 3: Run tests — confirm they all FAIL**

```bash
cd c:\Users\zhuol\Project\french_sle_simulator
python -m pytest tests/test_model_config.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` (module doesn't exist yet).

---

### Task 2: Create `tools/model_config.py`

**Files:**
- Create: `tools/model_config.py`

- [ ] **Step 1: Create the file**

```python
"""
Model configuration for SLE exam simulator tools.

Provides ModelConfig dataclass and load_default_configs() which reads
per-tool model settings from environment variables, falling back to
DEEPSEEK_API_KEY + deepseek-chat defaults.
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ModelConfig:
    api_key: str
    base_url: str
    model: str


def load_default_configs() -> "dict[str, ModelConfig]":
    """Read per-tool model config from env, falling back to DEEPSEEK_* vars."""
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_url = "https://api.deepseek.com"
    deepseek_model = "deepseek-chat"

    return {
        "generate": ModelConfig(
            api_key=os.getenv("GENERATE_API_KEY") or deepseek_key,
            base_url=os.getenv("GENERATE_BASE_URL") or deepseek_url,
            model=os.getenv("GENERATE_MODEL") or deepseek_model,
        ),
        "evaluate": ModelConfig(
            api_key=os.getenv("EVALUATE_API_KEY") or deepseek_key,
            base_url=os.getenv("EVALUATE_BASE_URL") or deepseek_url,
            model=os.getenv("EVALUATE_MODEL") or deepseek_model,
        ),
        "review": ModelConfig(
            api_key=os.getenv("REVIEW_API_KEY") or deepseek_key,
            base_url=os.getenv("REVIEW_BASE_URL") or deepseek_url,
            model=os.getenv("REVIEW_MODEL") or deepseek_model,
        ),
    }
```

- [ ] **Step 2: Run tests — confirm they all PASS**

```bash
python -m pytest tests/test_model_config.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tools/model_config.py tests/__init__.py tests/conftest.py tests/test_model_config.py
git commit -m "feat: add ModelConfig dataclass and load_default_configs()"
```

---

## Chunk 2: Update `tools/generate_exam.py`

### Task 3: Write failing tests for generate_exam wiring, then refactor

**Files:**
- Modify: `tests/test_model_config.py` → add `tests/test_generate_exam.py` (new file)
- Modify: `tools/generate_exam.py`

**Key lines in generate_exam.py:**
- Line 17: `from dotenv import load_dotenv`
- Line 19: `load_dotenv()`
- Lines 21–23: `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL` constants
- Line 149: `def generate_exam(num_questions: int) -> dict:`
- Line 159: API key guard
- Line 162: `client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)`
- Line 235: `model=DEEPSEEK_MODEL` inside `generate_exam`
- Line 348: `def regenerate_context(context_to_replace, existing_contexts, start_question_id, flagged_issues=None) -> dict:`
- Line 364: `client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)` inside `regenerate_context`
- Line 446: `model=DEEPSEEK_MODEL` inside `regenerate_context`

- [ ] **Step 1: Write failing tests for generate_exam wiring**

Create `tests/test_generate_exam.py`:

```python
"""Tests for ModelConfig wiring in tools/generate_exam.py"""
import pytest
from unittest.mock import patch, MagicMock
from tools.model_config import ModelConfig


def _make_valid_exam_response():
    """Minimal valid exam JSON the parser expects."""
    return {
        "contexts": [
            {
                "context_id": 1,
                "type": "fill_in_blank",
                "passage": "Il faut (1) ___ aller.",
                "questions": [
                    {
                        "question_id": 1,
                        "options": {"A": "y", "B": "en", "C": "lui", "D": "leur"},
                        "correct_answer": "A",
                        "grammar_topic": "pronoun",
                    }
                ],
            }
        ]
    }


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
```

- [ ] **Step 2: Run tests — confirm they FAIL**

```bash
python -m pytest tests/test_generate_exam.py -v
```

Expected: Tests fail because `generate_exam` doesn't accept `model_config` yet.

- [ ] **Step 3: Replace imports and constants in `generate_exam.py`**

At the top of `tools/generate_exam.py`, replace the dotenv block (lines 17–23):

```python
# Remove these lines:
from dotenv import load_dotenv
load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# Replace with (add after the existing 'import os' line):
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.model_config import ModelConfig, load_default_configs
```

- [ ] **Step 4: Update `generate_exam` signature and body**

Change the function signature at line 149:
```python
# Before:
def generate_exam(num_questions: int) -> dict:
# After:
def generate_exam(num_questions: int, model_config: ModelConfig = None) -> dict:
```

Replace the API key guard and client construction (lines 159–162):
```python
# Before:
if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "your_deepseek_key_here":
    raise ValueError("DEEPSEEK_API_KEY not configured in .env")
...
client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

# After — add cfg resolution BEFORE the guard:
cfg = model_config or load_default_configs()["generate"]
if not cfg.api_key or cfg.api_key == "your_deepseek_key_here":
    raise ValueError("No API key configured. Set DEEPSEEK_API_KEY (or GENERATE_API_KEY) in .env")
...
client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
```

Replace `model=DEEPSEEK_MODEL` (line ~235) with `model=cfg.model`.

- [ ] **Step 5: Update `regenerate_context` signature and body**

Change signature at line 348:
```python
# Before:
def regenerate_context(context_to_replace: dict, existing_contexts: list, start_question_id: int, flagged_issues: list = None) -> dict:
# After:
def regenerate_context(context_to_replace: dict, existing_contexts: list, start_question_id: int, flagged_issues: list = None, model_config: ModelConfig = None) -> dict:
```

At the top of the function body, add:
```python
cfg = model_config or load_default_configs()["generate"]
```

Replace client construction (line ~364):
```python
client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
```

Replace `model=DEEPSEEK_MODEL` (line ~446) with `model=cfg.model`.

- [ ] **Step 6: Verify no remaining module-level constant references**

```bash
grep -n "DEEPSEEK_BASE_URL\|DEEPSEEK_MODEL" tools/generate_exam.py
grep -n "= os.getenv..DEEPSEEK_API_KEY" tools/generate_exam.py
```

Expected: No output. (Note: the string literal `"DEEPSEEK_API_KEY"` appears in the error message — that is correct and expected.)

- [ ] **Step 7: Run tests — confirm they PASS**

```bash
python -m pytest tests/ -v
```

Expected: All tests PASS (both `test_model_config.py` and `test_generate_exam.py`).

- [ ] **Step 8: Smoke-test the import**

```bash
python -c "from tools.generate_exam import generate_exam, regenerate_context; print('OK')"
```

Expected: `OK`.

- [ ] **Step 9: Commit**

```bash
git add tools/generate_exam.py tests/test_generate_exam.py
git commit -m "feat: generate_exam accepts ModelConfig parameter"
```

---

## Chunk 3: Update `tools/evaluate_exam.py`

### Task 4: Refactor `evaluate_exam.py` to accept `ModelConfig`

**Files:**
- Modify: `tools/evaluate_exam.py`

**Key lines:**
- Lines 15–21: `load_dotenv()` and three `DEEPSEEK_*` constants
- Line 44: `def _generate_explanations(incorrect_items: list) -> dict:`
- Line 54: `client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)`
- Line 128: `model=DEEPSEEK_MODEL`
- Line 189: `def evaluate_exam(exam: dict, user_answers: dict) -> dict:`
- Lines 200–201: API key guard
- Line 356: `def regenerate_explanations(incorrect_items: list) -> dict:` (one-liner body)

- [ ] **Step 1: Replace imports and constants**

At the top of `tools/evaluate_exam.py`, replace lines 15–21:
```python
# Remove:
from dotenv import load_dotenv
load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# Replace with (after existing 'import os'):
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.model_config import ModelConfig, load_default_configs
```

- [ ] **Step 2: Update `_generate_explanations` signature and body**

Change signature at line 44:
```python
# Before:
def _generate_explanations(incorrect_items: list) -> dict:
# After:
def _generate_explanations(incorrect_items: list, model_config: ModelConfig) -> dict:
```

Replace client construction (line ~54):
```python
# Before:
client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
# After:
client = OpenAI(api_key=model_config.api_key, base_url=model_config.base_url)
```

Replace `model=DEEPSEEK_MODEL` (line ~128) with `model=model_config.model`.

- [ ] **Step 3: Update `evaluate_exam` signature and body**

Change signature at line 189:
```python
# Before:
def evaluate_exam(exam: dict, user_answers: dict) -> dict:
# After:
def evaluate_exam(exam: dict, user_answers: dict, model_config: ModelConfig = None) -> dict:
```

Replace the API key guard (lines 200–201) and resolve cfg before it:
```python
# Before:
if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "your_deepseek_key_here":
    raise ValueError("DEEPSEEK_API_KEY not configured in .env")

# After — add cfg resolution BEFORE the guard:
cfg = model_config or load_default_configs()["evaluate"]
if not cfg.api_key or cfg.api_key == "your_deepseek_key_here":
    raise ValueError("No API key configured. Set DEEPSEEK_API_KEY (or EVALUATE_API_KEY) in .env")
```

Find the call to `_generate_explanations` inside `evaluate_exam` and pass `cfg`:
```python
# Before:
explanations = _generate_explanations(incorrect_items)
# After:
explanations = _generate_explanations(incorrect_items, cfg)
```

- [ ] **Step 4: Update `regenerate_explanations` signature and body**

Change signature at line 356:
```python
# Before:
def regenerate_explanations(incorrect_items: list) -> dict:
# After:
def regenerate_explanations(incorrect_items: list, model_config: ModelConfig = None) -> dict:
```

Replace the one-liner body:
```python
# Before:
return _generate_explanations(incorrect_items)
# After:
cfg = model_config or load_default_configs()["evaluate"]
return _generate_explanations(incorrect_items, cfg)
```

- [ ] **Step 5: Verify no remaining module-level constant references**

```bash
grep -n "DEEPSEEK_BASE_URL\|DEEPSEEK_MODEL" tools/evaluate_exam.py
grep -n "= os.getenv..DEEPSEEK_API_KEY" tools/evaluate_exam.py
```

Expected: No output.

- [ ] **Step 6: Smoke-test the import**

```bash
python -c "from tools.evaluate_exam import evaluate_exam, regenerate_explanations; print('OK')"
```

Expected: `OK`.

- [ ] **Step 7: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 8: Commit**

```bash
git add tools/evaluate_exam.py
git commit -m "feat: evaluate_exam accepts ModelConfig parameter"
```

---

## Chunk 4: Update `tools/review_exam.py`

### Task 5: Refactor `review_exam.py` to accept `ModelConfig`

**Files:**
- Modify: `tools/review_exam.py`

**Key lines:**
- Lines 20–26: `load_dotenv()` and three `DEEPSEEK_*` constants
- Line 35: `def _call_review_api(system_prompt: str, user_prompt: str) -> dict:`
- Line 37: `client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)`
- Line 40: `model=DEEPSEEK_MODEL`
- Line 179: `def review_exam_quality(exam_data: dict) -> dict:`
- Line ~200: internal call `result = _call_review_api(EXAM_REVIEW_SYSTEM, user_prompt)`
- Line 285: `def review_feedback_quality(evaluation_data: dict) -> dict:`
- Line ~303: internal call `result = _call_review_api(FEEDBACK_REVIEW_SYSTEM, user_prompt)`

- [ ] **Step 1: Replace imports and constants**

At the top of `tools/review_exam.py`, replace lines 20–26:
```python
# Remove:
from dotenv import load_dotenv
load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# Replace with (after existing 'import os'):
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.model_config import ModelConfig, load_default_configs
```

- [ ] **Step 2: Update `_call_review_api` signature and body**

Change signature at line 35:
```python
# Before:
def _call_review_api(system_prompt: str, user_prompt: str) -> dict:
# After:
def _call_review_api(system_prompt: str, user_prompt: str, model_config: ModelConfig) -> dict:
```

Replace the client construction and model reference inside the function:
```python
# Before:
client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
...
    model=DEEPSEEK_MODEL,
# After:
client = OpenAI(api_key=model_config.api_key, base_url=model_config.base_url)
...
    model=model_config.model,
```

- [ ] **Step 3: Update `review_exam_quality` signature and internal call site**

Change signature at line 179:
```python
# Before:
def review_exam_quality(exam_data: dict) -> dict:
# After:
def review_exam_quality(exam_data: dict, model_config: ModelConfig = None) -> dict:
```

At the top of the function body (before the `try` block), add:
```python
cfg = model_config or load_default_configs()["review"]
```

Update the internal `_call_review_api` call (line ~200):
```python
# Before:
result = _call_review_api(EXAM_REVIEW_SYSTEM, user_prompt)
# After:
result = _call_review_api(EXAM_REVIEW_SYSTEM, user_prompt, cfg)
```

- [ ] **Step 4: Update `review_feedback_quality` signature and internal call site**

Change signature at line 285:
```python
# Before:
def review_feedback_quality(evaluation_data: dict) -> dict:
# After:
def review_feedback_quality(evaluation_data: dict, model_config: ModelConfig = None) -> dict:
```

At the top of the function body (before the `try` block), add:
```python
cfg = model_config or load_default_configs()["review"]
```

Update the internal `_call_review_api` call (line ~303):
```python
# Before:
result = _call_review_api(FEEDBACK_REVIEW_SYSTEM, user_prompt)
# After:
result = _call_review_api(FEEDBACK_REVIEW_SYSTEM, user_prompt, cfg)
```

- [ ] **Step 5: Verify no remaining module-level constant references**

```bash
grep -n "DEEPSEEK_BASE_URL\|DEEPSEEK_MODEL" tools/review_exam.py
grep -n "= os.getenv..DEEPSEEK_API_KEY" tools/review_exam.py
```

Expected: No output.

- [ ] **Step 6: Smoke-test the import**

```bash
python -c "from tools.review_exam import review_exam_quality, review_feedback_quality; print('OK')"
```

Expected: `OK`.

- [ ] **Step 7: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 8: Commit**

```bash
git add tools/review_exam.py
git commit -m "feat: review_exam accepts ModelConfig parameter"
```

---

## Chunk 5: Update `app.py` and `.env.template`

### Task 6: Wire `ModelConfig` into Streamlit UI and update `.env.template`

**Files:**
- Modify: `app.py` (import block ~line 15, session state ~line 26, `render_setup()`, `render_exam()`)
- Modify: `.env.template`

**Call site line numbers in app.py:**
- Line 104: `generate_exam(num_questions)`
- Line 108: `review_exam_quality(exam)` — initial exam review
- Line 128: `regenerate_context(ctx, exam["contexts"], start_qid, issues)`
- Line 138: `review_exam_quality(exam)` — re-review after regeneration
- Line 229: `evaluate_exam(exam, answers)`
- Line 241: `review_feedback_quality(evaluation)` — initial feedback review
- Line 284: `regenerate_explanations(items_to_regen)`
- Line 296: `review_feedback_quality(evaluation)` — re-review after regeneration

- [ ] **Step 1: Add import to `app.py`**

In `app.py`, add to the import block after line 17 (the last `from tools.X import` line):
```python
from tools.model_config import ModelConfig, load_default_configs
```

- [ ] **Step 2: Add session state initialization**

In the session state init block (after line 34), add:
```python
if "model_configs" not in st.session_state:
    st.session_state.model_configs = load_default_configs()
```

- [ ] **Step 3: Add model settings expander to `render_setup()`**

Inside `render_setup()`, after the `st.markdown(f"""...""")` display block and before the `col1, col2 = st.columns(2)` buttons, add:

```python
with st.expander("AI model settings (optional)"):
    for tool_key, label in [("generate", "Generation"), ("evaluate", "Evaluation"), ("review", "Review")]:
        cfg = st.session_state.model_configs[tool_key]
        st.markdown(f"**{label}**")
        col1, col2, col3 = st.columns(3)
        with col1:
            model = st.text_input("Model", value=cfg.model, key=f"{tool_key}_model")
        with col2:
            base_url = st.text_input("Base URL", value=cfg.base_url, key=f"{tool_key}_base_url")
        with col3:
            api_key = st.text_input("API Key", value="", placeholder="leave blank to use .env",
                                    type="password", key=f"{tool_key}_api_key")
        # Runs on every Streamlit rerun. The 'api_key or cfg.api_key' guard prevents
        # a blank password field from overwriting a key already stored in session state.
        st.session_state.model_configs[tool_key] = ModelConfig(
            model=model,
            base_url=base_url,
            api_key=api_key or cfg.api_key,
        )
```

- [ ] **Step 4: Update 4 call sites in `render_setup()`**

```python
# Line 104:
exam = generate_exam(num_questions, model_config=st.session_state.model_configs["generate"])

# Line 108:
review = review_exam_quality(exam, model_config=st.session_state.model_configs["review"])

# Line 128:
new_ctx = regenerate_context(ctx, exam["contexts"], start_qid, issues,
                             model_config=st.session_state.model_configs["generate"])

# Line 138:
review = review_exam_quality(exam, model_config=st.session_state.model_configs["review"])
```

- [ ] **Step 5: Update 4 call sites in `render_exam()`**

```python
# Line 229:
evaluation = evaluate_exam(exam, answers, model_config=st.session_state.model_configs["evaluate"])

# Line 241:
feedback_review = review_feedback_quality(evaluation, model_config=st.session_state.model_configs["review"])

# Line 284:
new_expls = regenerate_explanations(items_to_regen, model_config=st.session_state.model_configs["evaluate"])

# Line 296:
feedback_review = review_feedback_quality(evaluation, model_config=st.session_state.model_configs["review"])
```

- [ ] **Step 6: Verify all 8 call sites have `model_config=`**

```bash
grep -n "model_config=" app.py
```

Expected: 8 lines, one for each call site.

- [ ] **Step 7: Update `.env.template`**

Append to `.env.template` after the `DEEPSEEK_API_KEY` block:

```bash
# ── Per-tool model overrides (all optional) ──────────────────────────────────
# If not set, each tool falls back to DEEPSEEK_API_KEY + deepseek-chat defaults.
# Any OpenAI-compatible endpoint is supported (base_url + api_key + model).
# Empty values (e.g. GENERATE_API_KEY=) are treated the same as absent — both
# fall back to DEEPSEEK_API_KEY.
#
# Examples:
#   GENERATE_BASE_URL=https://api.openai.com/v1
#   GENERATE_MODEL=gpt-4o
#   GENERATE_API_KEY=sk-...

GENERATE_API_KEY=
GENERATE_BASE_URL=
GENERATE_MODEL=

EVALUATE_API_KEY=
EVALUATE_BASE_URL=
EVALUATE_MODEL=

REVIEW_API_KEY=
REVIEW_BASE_URL=
REVIEW_MODEL=
```

- [ ] **Step 8: Smoke-test the full app import**

```bash
python -c "import app; print('OK')"
```

Expected: `OK`.

- [ ] **Step 9: Manual UI verification**

Run the app and verify:
```bash
streamlit run app.py
```

1. Open setup screen — confirm no visual change (expander is collapsed)
2. Expand "AI model settings (optional)" — confirm 3 sections (Generation / Evaluation / Review), each with Model / Base URL / API Key fields pre-filled from env defaults
3. Change Generation model to `deepseek-reasoner` — confirm it persists on the next Streamlit interaction
4. Enter a value in an API Key field — confirm it shows as `•••••`
5. Click "Generate exam" — confirm exam generates normally

- [ ] **Step 10: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 11: Commit**

```bash
git add app.py .env.template
git commit -m "feat: add per-tool model selection UI and wire ModelConfig to all call sites"
```

---

## Final Verification

- [ ] **Run full tests one last time**

```bash
python -m pytest tests/ -v
```

- [ ] **Verify no module-level DEEPSEEK constants remain in tool files**

```bash
grep -rn "DEEPSEEK_BASE_URL\|DEEPSEEK_MODEL" tools/
grep -rn "= os.getenv..DEEPSEEK_API_KEY" tools/
```

Expected: No output from either command. (`model_config.py` uses `os.getenv("DEEPSEEK_API_KEY")` as a string argument — the `= os.getenv(` pattern ensures only the assignment form is caught.)

- [ ] **Final commit if any cleanup needed**

```bash
git add -A
git commit -m "chore: model selection feature complete"
```
