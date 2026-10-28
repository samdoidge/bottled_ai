"""Core AI logic: ask_ai() and response parsing."""
import json
import re
import time
import sys
from typing import Optional, List, Dict, Any

from rs.ai.llm_advisor.config import (
    ENABLED, MAX_RETRIES, MODEL, MAX_TOKENS, TEMPERATURE, LOG_FILE, API_TIMEOUT
)
from rs.ai.llm_advisor.client import get_client
from rs.ai.llm_advisor.prompts import SYSTEM_PROMPT


def log(msg: str):
    """Log to file and stderr."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass
    print(f"[LLM] {msg}", file=sys.stderr)


def log_new_game():
    """Log new game separator."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    separator = "\n" + "=" * 60 + "\n" + " " * 20 + "NEW GAME\n" + "=" * 60
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(f"[{ts}] {separator}\n")
    except Exception:
        pass


def is_enabled(decision_type: str) -> bool:
    """Check if AI is enabled for this decision type."""
    return bool(get_client()) and ENABLED.get(decision_type, False)


def parse_response(text: str, num_choices: int, choices: List[str] = None) -> Optional[int]:
    """Extract choice index from AI response. Returns None on failure.

    If choices list is provided, also tries to match option names in text.
    """
    # Try JSON parsing first
    try:
        clean = text
        if "```" in clean:
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        data = json.loads(clean)
        idx = int(data.get("choice", -1))
        if 0 <= idx < num_choices:
            return idx
    except Exception:
        pass

    # Regex fallback for "choice": N
    m = re.search(r'"choice"\s*:\s*"?(\d+)"?', text)
    if m:
        idx = int(m.group(1))
        if 0 <= idx < num_choices:
            return idx

    # Try natural language patterns (for reasoning content)
    # Look for "option 0", "choice 1", "pick 2", "select 0", "I'll take 1"
    patterns = [
        r'(?:option|choice|pick|select|choose|take)\s*[:#]?\s*(\d+)',
        r'(\d+)\s*(?:is the best|is optimal|would be best)',
        r'(?:best|optimal|right)\s*(?:choice|option)\s*(?:is|would be)?\s*(\d+)',
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            idx = int(m.group(1))
            if 0 <= idx < num_choices:
                return idx

    # Last resort: standalone number on a line
    for line in text.split("\n"):
        if line.strip().isdigit():
            idx = int(line.strip())
            if 0 <= idx < num_choices:
                return idx

    # If choices provided, look for option names mentioned with positive sentiment
    # Focus on the last portion of text where conclusions usually are
    if choices:
        last_portion = text[-1500:] if len(text) > 1500 else text
        for i, choice in enumerate(choices):
            # Get the card/option name (text before parenthesis, colon, or hyphen)
            # e.g., "Shrug It Off (1): ..." -> "Shrug It Off"
            name_match = re.match(r'^([A-Za-z][A-Za-z\s\']+?)(?:\s*[\(:\-]|$)', choice)
            if name_match:
                name = name_match.group(1).strip().lower()
                if len(name) < 3:  # Skip very short names
                    continue
                # Look for positive mentions like "X is good", "take X", "pick X", "choose X"
                # Use (?:\s+\w+){0,3} to allow up to 3 words between name and sentiment
                positive_patterns = [
                    rf'{re.escape(name)}(?:\s+\w+){{0,3}}\s+(?:good|strong|solid|best|great|premium|excellent)',
                    rf'(?:take|pick|choose|want|go with)\s+{re.escape(name)}',
                    rf'{re.escape(name)}\s+(?:is the|would be|seems|provides)',
                ]
                for pattern in positive_patterns:
                    if re.search(pattern, last_portion, re.IGNORECASE):
                        return i

    return None


def ask_ai(
    decision_type: str,
    choices: List[str],
    context: Dict[str, Any],
    mode_prompt: str,
) -> Optional[int]:
    """Ask AI to pick from choices. Returns index or None on failure.

    Args:
        decision_type: Type of decision (card_reward, upgrade, etc.)
        choices: List of options to choose from
        context: Game state context dict
        mode_prompt: Mode-specific prompt rules (combined with SYSTEM_PROMPT)
    """
    if not is_enabled(decision_type):
        return None

    client = get_client()
    if not client:
        return None

    # Log new game on neow
    if decision_type == "neow":
        log_new_game()

    # Combine system prompt with mode-specific rules
    full_system_prompt = SYSTEM_PROMPT + "\n\n" + mode_prompt

    choices_str = "\n".join(f"{i}: {c}" for i, c in enumerate(choices))
    user_prompt = f"OPTIONS:\n{choices_str}\n\nCONTEXT:\n{json.dumps(context, separators=(',', ':'))}"

    # Log request details
    log(f"[{decision_type}] Choices: {choices}")
    log(f"[{decision_type}] Context: {json.dumps(context, separators=(',', ':'))}")

    for attempt in range(MAX_RETRIES):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                timeout=API_TIMEOUT,  # Pass timeout per-request to override cached client
                messages=[
                    {"role": "system", "content": full_system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            message = resp.choices[0].message

            # Log reasoning content if present (deepseek-reasoner)
            reasoning = getattr(message, 'reasoning_content', None)
            if reasoning and isinstance(reasoning, str):
                reasoning_preview = reasoning[:500] + "..." if len(reasoning) > 500 else reasoning
                log(f"[{decision_type}] Reasoning ({len(reasoning)} chars): {reasoning_preview}")

            text = (message.content or "").strip()
            log(f"[{decision_type}] Response: {text}")

            # Try parsing content first
            idx = parse_response(text, len(choices), choices)
            if idx is not None:
                log(f"[{decision_type}] => Chose {idx}: {choices[idx]}")
                return idx

            # If content empty/unparseable, try extracting choice from reasoning
            if reasoning and isinstance(reasoning, str) and not text:
                reasoning_end = reasoning[-300:] if len(reasoning) > 300 else reasoning
                log(f"[{decision_type}] Content empty, parsing reasoning end: ...{reasoning_end}")
                idx = parse_response(reasoning, len(choices), choices)
                if idx is not None:
                    log(f"[{decision_type}] => Chose {idx} (from reasoning): {choices[idx]}")
                    return idx
        except Exception as e:
            log(f"[{decision_type}] Error {attempt+1}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(0.5)

    return None
