"""
Model configuration for SLE exam simulator tools.

Provides ModelConfig dataclass and load_default_configs() which reads
per-tool model settings from environment variables, falling back to
DEEPSEEK_API_KEY + deepseek-v4-pro defaults.
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


MODEL_BASE_URLS: "dict[str, str]" = {
    "deepseek-v4-pro": "https://api.deepseek.com",
    "deepseek-v4-flash": "https://api.deepseek.com",
    "gemini-3-flash-preview": "https://generativelanguage.googleapis.com/v1beta/openai/",
}


@dataclass
class ModelConfig:
    api_key: str
    base_url: str
    model: str


def get_provider_default_key(base_url: str) -> str:
    """Return the best-matching API key from env for a given provider base URL."""
    if "deepseek.com" in base_url:
        return os.getenv("DEEPSEEK_API_KEY", "")
    if "googleapis.com" in base_url:
        return os.getenv("GOOGLE_API_KEY") or os.getenv("GENERATE_API_KEY", "")
    if "openai.com" in base_url:
        return os.getenv("OPENAI_API_KEY", "")
    return os.getenv("DEEPSEEK_API_KEY", "")


def load_default_configs() -> "dict[str, ModelConfig]":
    """Read per-tool model config from env, falling back to DEEPSEEK_* vars."""
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_url = "https://api.deepseek.com"
    deepseek_model = "deepseek-v4-pro"

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
        "flashcard": ModelConfig(
            api_key=os.getenv("FLASHCARD_API_KEY") or deepseek_key,
            base_url=os.getenv("FLASHCARD_BASE_URL") or deepseek_url,
            model=os.getenv("FLASHCARD_MODEL") or deepseek_model,
        ),
    }
