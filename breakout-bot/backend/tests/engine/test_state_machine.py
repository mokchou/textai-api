"""Machine à états : chaque transition légale passe, toute autre lève."""

from __future__ import annotations

import pytest

from app.engine.state_machine import TRANSITIONS, IllegalTransition, transition
from app.engine.types import EngineState, TradeState


def test_cycle_mode1_confirme():
    st = EngineState()
    transition(st, "range_arme")
    assert st.state is TradeState.RANGE_ARME
    transition(st, "fill_mode1")
    assert st.state is TradeState.EN_POSITION_NON_CONFIRMEE
    transition(st, "confirme")
    assert st.state is TradeState.EN_POSITION
    transition(st, "cloture")
    assert st.state is TradeState.INACTIF


def test_cycle_mode1_avorte():
    st = EngineState()
    transition(st, "range_arme")
    transition(st, "fill_mode1")
    transition(st, "cloture")  # sortie avortée à l'open suivant
    assert st.state is TradeState.INACTIF


def test_cycle_mode2_et_timeout():
    st = EngineState()
    transition(st, "range_arme")
    transition(st, "timeout_retest")
    assert st.state is TradeState.INACTIF
    transition(st, "range_arme")
    transition(st, "fill_mode2")
    assert st.state is TradeState.EN_POSITION


def test_toutes_les_transitions_illegales_levent():
    events = {e for (_, e) in TRANSITIONS}
    for state in TradeState:
        for event in events:
            st = EngineState()
            st.state = state
            if (state, event) in TRANSITIONS:
                transition(st, event)
                assert st.state is TRANSITIONS[(state, event)]
            else:
                with pytest.raises(IllegalTransition):
                    transition(st, event)
