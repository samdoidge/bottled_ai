"""LLM advisor configuration. DeepSeek defaults; any OpenAI-compatible endpoint works."""
import os
from pathlib import Path


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# API settings
API_KEY = os.environ.get("LLM_API_KEY", "")
API_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
API_TIMEOUT = _int_env("LLM_TIMEOUT", 30)
MAX_RETRIES = 2

# Per-decision switches. Only decisions with an LLM handler can be enabled.
ENABLED = {
    "card_reward": True,
}

# Model settings
MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")
MAX_TOKENS = _int_env("LLM_MAX_TOKENS", 500)
TEMPERATURE = _float_env("LLM_TEMPERATURE", 0.2)
LOG_FILE = Path(__file__).parent.parent.parent.parent / "logs" / "llm_advisor.log"
