# Model Selection Feature — Design Spec
**Date:** 2026-03-12
**Status:** Approved

## Overview

Allow users to configure any OpenAI-compatible AI model independently for each of the three tools: exam generation, evaluation, and review. Environment variables set defaults; the Streamlit setup screen allows per-session overrides.

## Requirements

- **Provider support:** Any OpenAI-compatible endpoint (user supplies `base_url`, `api_key`, `model`)
- **Configuration scope:** Per-tool — generation, evaluation, and review each have independent configs
- **Configuration source:** `.env` sets defaults; Streamlit setup screen allows per-session overrides
- **Backward compatibility:** Existing `.env` with only `DEEPSEEK_API_KEY` continues to work with no changes

---

## Section 1: New Module — `tools/model_config.py`

A new file holds the `ModelConfig` dataclass and env-loading logic. This is the single source of truth for model configuration across all tools.

```python
from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class ModelConfig:
    api_key: str
    base_url: str
    model: str

def load_default_configs() -> dict[str, ModelConfig]:
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

If a per-tool env var is absent or empty, it silently falls back to `DEEPSEEK_API_KEY` + DeepSeek defaults. No existing `.env` file requires changes.

---

## Section 2: Tool Function Signature Changes

Each tool drops its module-level `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, and `DEEPSEEK_MODEL` constants and accepts a `model_config: ModelConfig = None` parameter. When `None`, the function resolves the config from env via `load_default_configs()` — preserving backward compatibility for direct script usage.

### `tools/generate_exam.py`

```python
from tools.model_config import ModelConfig, load_default_configs

def generate_exam(num_questions: int, model_config: ModelConfig = None) -> dict:
    cfg = model_config or load_default_configs()["generate"]
    client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
    # use cfg.model in API call

def regenerate_context(ctx, all_contexts, start_qid, issues,
                       model_config: ModelConfig = None) -> dict:
    cfg = model_config or load_default_configs()["generate"]
```

### `tools/evaluate_exam.py`

```python
def evaluate_exam(exam, answers, model_config: ModelConfig = None) -> dict:
    cfg = model_config or load_default_configs()["evaluate"]

def regenerate_explanations(items, model_config: ModelConfig = None) -> dict:
    cfg = model_config or load_default_configs()["evaluate"]
```

### `tools/review_exam.py`

```python
def review_exam_quality(exam_data, model_config: ModelConfig = None) -> dict:
    cfg = model_config or load_default_configs()["review"]

def review_feedback_quality(evaluation_data, model_config: ModelConfig = None) -> dict:
    cfg = model_config or load_default_configs()["review"]

def _call_review_api(system_prompt, user_prompt, model_config: ModelConfig) -> dict:
    # model_config is required here — always called from the two public functions
    # which have already resolved the config
    client = OpenAI(api_key=model_config.api_key, base_url=model_config.base_url)
    # use model_config.model
```

---

## Section 3: Streamlit UI Changes (`app.py`)

### Session state initialization

At app startup, alongside existing state keys:

```python
if "model_configs" not in st.session_state:
    st.session_state.model_configs = load_default_configs()
    # keys: "generate", "evaluate", "review"
```

### Setup screen — model settings expander

Added below the question count selector, before the action buttons. Collapsed by default so the UI is unchanged for normal use:

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
        st.session_state.model_configs[tool_key] = ModelConfig(
            model=model,
            base_url=base_url,
            api_key=api_key or cfg.api_key,  # blank → keep env value
        )
```

### Tool call sites

Six call sites in `render_setup()` and `render_exam()` updated to pass session configs:

```python
# Generation
exam = generate_exam(num_questions, model_config=st.session_state.model_configs["generate"])
review = review_exam_quality(exam, model_config=st.session_state.model_configs["review"])
new_ctx = regenerate_context(..., model_config=st.session_state.model_configs["generate"])

# Evaluation
evaluation = evaluate_exam(exam, answers, model_config=st.session_state.model_configs["evaluate"])
feedback_review = review_feedback_quality(evaluation, model_config=st.session_state.model_configs["review"])
new_expls = regenerate_explanations(items, model_config=st.session_state.model_configs["evaluate"])
```

---

## Section 4: `.env.template` Updates

The existing `DEEPSEEK_API_KEY` variable is unchanged. Nine optional per-tool vars are added:

```bash
# ── Per-tool model overrides (all optional) ──────────────────────────────────
# If not set, each tool falls back to DEEPSEEK_API_KEY + deepseek-chat defaults.
# Any OpenAI-compatible endpoint is supported (base_url + api_key + model).
#
# Examples:
#   GENERATE_BASE_URL=https://api.openai.com/v1
#   GENERATE_MODEL=gpt-4o
#   GENERATE_API_KEY=sk-...
#
#   REVIEW_BASE_URL=https://api.deepseek.com
#   REVIEW_MODEL=deepseek-chat

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

---

## Files Changed

| File | Change |
|------|--------|
| `tools/model_config.py` | **New file** — `ModelConfig` dataclass + `load_default_configs()` |
| `tools/generate_exam.py` | Drop 3 module-level constants; update 2 function signatures |
| `tools/evaluate_exam.py` | Drop 3 module-level constants; update 2 function signatures |
| `tools/review_exam.py` | Drop 3 module-level constants; update 3 function signatures |
| `app.py` | Init session state; add UI expander; pass configs to 6 call sites |
| `.env.template` | Add 9 optional per-tool vars with comments |

## Out of Scope

- Validation that the user-supplied model/endpoint actually works before exam generation starts
- Persisting per-session model choices across browser refreshes
- Support for non-OpenAI-compatible APIs (e.g. native Anthropic SDK)
