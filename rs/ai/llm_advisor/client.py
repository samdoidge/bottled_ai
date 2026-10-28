"""Lazy OpenAI-compatible client. Disabled cleanly when unconfigured."""
import sys

from rs.ai.llm_advisor.config import API_KEY, API_BASE_URL, API_TIMEOUT

_client = None
_warned = False


def _warn_once(message: str) -> None:
    global _warned
    if not _warned:
        print(f"[llm_advisor] {message}", file=sys.stderr)
        _warned = True


def get_client():
    """Return an OpenAI-compatible client, or None when unavailable."""
    global _client
    if _client is not None:
        return _client

    if not API_KEY:
        _warn_once("LLM_API_KEY is not set; advisor disabled")
        return None

    try:
        from openai import OpenAI
    except ImportError:
        _warn_once("openai is not installed; run 'pip install openai'")
        return None

    try:
        _client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL, timeout=API_TIMEOUT)
    except Exception as exc:  # pragma: no cover - depends on local environment
        _warn_once(f"could not initialise the LLM client: {exc}")
        return None

    return _client
