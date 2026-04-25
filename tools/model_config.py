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
    }
