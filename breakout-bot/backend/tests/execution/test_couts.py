"""Frais, slippage et funding : décomposition auditable des coûts (PRD §6)."""

from __future__ import annotations

import numpy as np
import pytest

from app.config.models import BotConfig
from app.engine.types import Direction, EngineState, EntryMode, Position, TradeState
from app.execution.simulator import ExecutionSimulator
from app.execution.slippage import slippage_amount
from tests.fixtures.candles import TF_15M_MS, make_market


def test_slippage_fixe_volatilite_stress():
    cfg = BotConfig()
    assert slippage_amount(100.0, 2.0, cfg.costs) == pytest.approx(100.0 * 4 / 10_000)
    cfg.costs.slippage_model = "volatilite"
    assert slippage_amount(100.0, 2.0, cfg.costs) == pytest.approx(
        cfg.costs.slippage_atr_coef * 2.0
    )
    cfg.costs.slippage_model = "stress"
    assert slippage_amount(100.0, 2.0, cfg.costs) == pytest.approx(
        100.0 * 4 / 10_000 * cfg.costs.stress_multiplier
    )


def _position(direction: Direction, entry: float, stop: float) -> Position:
    return Position(
        direction=direction,
        mode=EntryMode.MODE_1,
        qty=2.0,
        entry_price=entry,
        entry_ts=0,
        entry_index=0,
        stop_price=stop,
        initial_risk=abs(entry - stop),
        confirmed=True,
    )


def test_funding_long_paie_short_encaisse():
    # 33 bougies M15 : la 32e (08:00 UTC) porte une échéance de funding +0,01 %
    candles = [(100.0, 100.1, 99.9, 100.0, 10.0)] * 34
    md = make_market(candles, funding_rate_pct=0.01)
    assert md.ts[32] % (8 * 3600 * 1000) == 0
    cfg = BotConfig()
    sim = ExecutionSimulator(cfg, md, np.full(len(md), 1.0))

    st = EngineState(equity=10_000.0)
    st.state = TradeState.EN_POSITION
    st.position = _position(Direction.LONG, 100.0, 95.0)
    for i in range(1, 34):
        sim.process_candle(st, i)
    expected = 2.0 * 100.0 * 0.01 / 100.0  # qty × prix × taux
    assert st.position.funding_paid == pytest.approx(expected)
    assert not sim.fallback_funding_used

    st2 = EngineState(equity=10_000.0)
    st2.state = TradeState.EN_POSITION
    st2.position = _position(Direction.SHORT, 100.0, 105.0)
    sim2 = ExecutionSimulator(cfg, md, np.full(len(md), 1.0))
    for i in range(1, 34):
        sim2.process_candle(st2, i)
    assert st2.position.funding_paid == pytest.approx(-expected)  # le short encaisse


def test_funding_fallback_signale():
    candles = [(100.0, 100.1, 99.9, 100.0, 10.0)] * 34
    md = make_market(candles)  # pas d'historique de funding ⇒ NaN aux échéances
    cfg = BotConfig()
    sim = ExecutionSimulator(cfg, md, np.full(len(md), 1.0))
    st = EngineState(equity=10_000.0)
    st.state = TradeState.EN_POSITION
    st.position = _position(Direction.LONG, 100.0, 95.0)
    for i in range(1, 34):
        sim.process_candle(st, i)
    assert sim.fallback_funding_used  # le rapport doit signaler le taux de repli
    expected = 2.0 * 100.0 * cfg.costs.fallback_funding_pct / 100.0
    assert st.position.funding_paid == pytest.approx(expected)


def test_decomposition_pnl_brut_vers_net():
    """PnL brut → frais entrée → frais sortie → slippage → funding → PnL net."""
    candles = [(100.0, 100.1, 99.9, 100.0, 10.0)] * 40
    md = make_market(candles, funding_rate_pct=0.01)
    cfg = BotConfig()
    sim = ExecutionSimulator(cfg, md, np.full(len(md), 1.0))
    st = EngineState(equity=10_000.0)
    st.state = TradeState.EN_POSITION
    pos = _position(Direction.LONG, 99.0, 95.0)
    pos.entry_fee = 99.0 * 2.0 * cfg.costs.taker_fee_pct / 100.0
    pos.entry_slippage = 0.05
    st.position = pos
    # franchit l'échéance de funding (i=32) puis stop touché à i=35
    md.low[35] = 94.0
    trades = []
    for i in range(1, 36):
        trades += sim.process_candle(st, i)
    assert len(trades) == 1
    t = trades[0]
    assert t.pnl_net == pytest.approx(
        t.pnl_gross - t.entry_fee - t.exit_fee - t.slippage_cost - t.funding_cost
    )
    assert t.funding_cost > 0  # le long a payé le funding positif
    assert t.exit_fee == pytest.approx(t.exit_price * t.qty * cfg.costs.taker_fee_pct / 100.0)


def test_horodatage_funding_aligne():
    assert (TF_15M_MS * 32) % (8 * 3600 * 1000) == 0
