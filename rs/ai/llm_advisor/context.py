"""Build context dicts for AI prompts. Keep context minimal but useful."""
from typing import List, Dict, Any
from rs.machine.state import GameState


def build_card_reward_context(state: GameState) -> Dict[str, Any]:
    """Build minimal context for card reward decisions."""
    gs = state.game_state() or {}
    deck = state.get_deck_card_list_by_name_with_upgrade_stripped()

    ctx = {
        "deck_size": sum(deck.values()),
        "deck": dict(deck),
        "relics": state.get_relics()[:12],
        "floor": state.floor(),
    }

    # Add act
    act = gs.get("act_boss") or gs.get("act")
    if act:
        ctx["act"] = act

    # Add HP if available
    hp = gs.get("current_hp")
    max_hp = gs.get("max_hp")
    if hp and max_hp:
        ctx["hp"] = hp
        ctx["max_hp"] = max_hp
        ctx["hp_pct"] = round(hp / max_hp, 2)

    return ctx


def build_boss_relic_context(state: GameState) -> Dict[str, Any]:
    """Build context for boss relic decisions."""
    gs = state.game_state() or {}
    deck = state.get_deck_card_list_by_name_with_upgrade_stripped()

    return {
        "deck": dict(deck),
        "deck_size": sum(deck.values()),
        "relics": state.get_relics()[:12],
        "hp": gs.get("current_hp"),
        "max_hp": gs.get("max_hp"),
    }


def build_event_context(state: GameState, gold: int = None) -> Dict[str, Any]:
    """Build context for event decisions."""
    ctx = build_card_reward_context(state)
    if gold is not None:
        ctx["gold"] = gold
    return ctx


def build_upgrade_context(state: GameState) -> Dict[str, Any]:
    """Build context for upgrade decisions."""
    return build_card_reward_context(state)
