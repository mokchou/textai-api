"""Machine à états d'un trade (PRD §5.1) : transitions explicites et gardées.

Toute transition non listée lève — un bug de logique ne peut pas passer
silencieusement.
"""

from __future__ import annotations

from app.engine.types import EngineState, TradeState

# (état courant, événement) -> nouvel état
TRANSITIONS: dict[tuple[TradeState, str], TradeState] = {
    (TradeState.INACTIF, "range_arme"): TradeState.RANGE_ARME,
    (TradeState.RANGE_ARME, "desarme"): TradeState.INACTIF,
    (TradeState.RANGE_ARME, "fill_mode1"): TradeState.EN_POSITION_NON_CONFIRMEE,
    (TradeState.RANGE_ARME, "fill_mode2"): TradeState.EN_POSITION,
    (TradeState.RANGE_ARME, "timeout_retest"): TradeState.INACTIF,
    (TradeState.EN_POSITION_NON_CONFIRMEE, "confirme"): TradeState.EN_POSITION,
    (TradeState.EN_POSITION_NON_CONFIRMEE, "cloture"): TradeState.INACTIF,
    (TradeState.EN_POSITION, "cloture"): TradeState.INACTIF,
}


class IllegalTransition(RuntimeError):
    pass


def transition(state: EngineState, event: str) -> None:
    key = (state.state, event)
    if key not in TRANSITIONS:
        raise IllegalTransition(f"transition interdite : {state.state.value} --{event}-->")
    state.state = TRANSITIONS[key]
