"""Example LLM-powered card reward handler."""
from typing import Optional

from presentation_config import presentation_mode, p_delay
from rs.game.screen_type import ScreenType
from rs.machine.command import Command
from rs.machine.handlers.handler import Handler
from rs.machine.handlers.handler_action import HandlerAction
from rs.machine.state import GameState

from rs.ai.llm_advisor.core import ask_ai, is_enabled, log
from rs.ai.llm_advisor.prompts import CARD_REWARD
from rs.ai.llm_advisor.context import build_card_reward_context


class CardRewardHandler(Handler):
    """Card reward handler that asks the LLM for a decision."""

    def can_handle(self, state: GameState) -> bool:
        return (
            state.has_command(Command.CHOOSE)
            and state.screen_type() == ScreenType.CARD_REWARD.value
            and state.game_state().get("room_phase") in ("COMPLETE", "EVENT", "COMBAT")
        )

    def handle(self, state: GameState) -> HandlerAction:
        choice_list = state.get_choice_list()

        # Try AI decision
        ai_choice = self._ask_ai(state, choice_list)

        if ai_choice is not None:
            return self._make_action(ai_choice, choice_list, state)

        # Fallback: take the first card if possible; never silently skip every reward.
        log("[card_reward] AI unavailable, falling back to first option")
        if choice_list:
            return self._make_action(0, choice_list, state)
        return self._skip_action(state)

    def _ask_ai(self, state: GameState, choice_list: list) -> Optional[int]:
        """Ask AI for card choice."""
        if not is_enabled("card_reward"):
            return None

        choices = list(choice_list)
        if state.has_command(Command.SKIP):
            choices.append("SKIP (take no card)")
        context = build_card_reward_context(state)

        return ask_ai("card_reward", choices, context, CARD_REWARD)

    def _make_action(self, idx: int, choice_list: list, state: GameState) -> HandlerAction:
        """Convert choice index to HandlerAction."""
        # If chose SKIP (last option we added)
        if idx >= len(choice_list):
            return self._skip_action(state)

        if choice_list[idx] == "bowl":
            cmd = "choose bowl"
        else:
            cmd = f"choose {idx}"
        if presentation_mode:
            return HandlerAction(commands=[p_delay, cmd, "wait 30"])
        return HandlerAction(commands=[cmd, "wait 30"])

    def _skip_action(self, state: GameState) -> HandlerAction:
        """Generate skip/proceed action."""
        room_phase = state.game_state().get("room_phase")

        if room_phase == "COMBAT":
            return HandlerAction(commands=["skip"])
        if room_phase == "EVENT" and state.floor() != "0":
            return HandlerAction(commands=["skip"])

        if presentation_mode:
            return HandlerAction(commands=[p_delay, "skip", "proceed"])
        return HandlerAction(commands=["skip", "proceed"])
