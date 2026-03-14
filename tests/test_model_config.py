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
