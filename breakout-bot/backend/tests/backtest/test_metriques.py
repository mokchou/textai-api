"""Métriques, ventilations et attribution des coûts (PRD §11)."""

from __future__ import annotations

import numpy as np
import pytest

from app.engine.types import Direction, EntryMode, ExitReason, Trade
from app.metrics.breakdowns import compute_breakdowns
from app.metrics.compute import compute_metrics
from app.metrics.cost_attribution import cost_attribution


def make_trade(
    pnl_net: float,
    direction: Direction = Direction.LONG,
    mode: EntryMode = EntryMode.MODE_1,
    aborted: bool = False,
    fees: float = 1.0,
    slippage: float = 0.5,
    funding: float = 0.25,
    entry_ts: int = 0,
    exit_ts: int = 3_600_000,
) -> Trade:
    gross = pnl_net + fees + slippage + funding
    return Trade(
        symbol="TESTUSDT",
        direction=direction,
        mode=mode,
        entry_ts=entry_ts,
        exit_ts=exit_ts,
        entry_index=0,
        exit_index=4,
        entry_price=100.0,
        exit_price=100.0 + gross,
        qty=1.0,
        exit_reason=ExitReason.AVORTE if aborted else ExitReason.TRAILING,
        aborted=aborted,
        pnl_gross=gross,
        entry_fee=fees / 2,
        exit_fee=fees / 2,
        slippage_cost=slippage,
        funding_cost=funding,
        pnl_net=pnl_net,
        r_multiple=pnl_net / 75.0,
        mae=0.4,
        mfe=1.2,
    )


@pytest.fixture
def trades() -> list[Trade]:
    day = 24 * 3_600_000
    return [
        make_trade(50.0, entry_ts=0, exit_ts=day),
        make_trade(
            -30.0,
            direction=Direction.SHORT,
            mode=EntryMode.MODE_2,
            entry_ts=2 * day,
            exit_ts=3 * day,
        ),
        make_trade(80.0, entry_ts=5 * day, exit_ts=6 * day),
        make_trade(-5.0, aborted=True, entry_ts=8 * day, exit_ts=8 * day + 3_600_000),
    ]


def test_metriques_globales(trades):
    ts = np.arange(0, 10 * 96, dtype=np.int64) * 900_000
    equity = np.full(len(ts), 10_000.0)
    m = compute_metrics(trades, equity, ts, 10_000.0)
    assert m["nb_trades"] == 4
    assert m["nb_avortes"] == 1
    assert m["pnl_net"] == pytest.approx(95.0)
    assert m["win_rate_pct"] == pytest.approx(50.0)
    assert m["profit_factor"] == pytest.approx(130.0 / 35.0)
    assert m["total_frais"] == pytest.approx(4.0)
    assert m["total_slippage"] == pytest.approx(2.0)
    assert m["total_funding"] == pytest.approx(1.0)


def test_drawdown_montant_duree_date():
    ts = np.arange(6, dtype=np.int64) * 900_000
    equity = np.array([100.0, 110.0, 90.0, 95.0, 120.0, 118.0])
    m = compute_metrics([], equity, ts, 100.0)
    assert m["max_drawdown"] == pytest.approx(20.0)
    assert m["max_drawdown_pct"] == pytest.approx(20.0 / 110.0 * 100.0)
    assert m["max_drawdown_date"] == int(ts[2])


def test_ventilations_par_sous_ensemble(trades):
    ts = np.arange(0, 10 * 96, dtype=np.int64) * 900_000
    equity = np.full(len(ts), 10_000.0)
    b = compute_breakdowns(trades, equity, ts, 10_000.0)
    assert b["long"]["nb_trades"] == 3
    assert b["short"]["nb_trades"] == 1
    assert b["mode_2"]["nb_trades"] == 1
    assert b["avortes"]["nb_trades"] == 1
    assert b["short"]["pnl_net"] == pytest.approx(-30.0)


def test_attribution_des_couts_et_alerte(trades):
    rep = cost_attribution(trades, fallback_funding_used=True)
    assert rep["pnl_brut"] == pytest.approx(102.0)
    assert rep["pnl_net"] == pytest.approx(95.0)
    assert rep["ratio_couts_pct"] == pytest.approx(7.0 / 102.0 * 100.0)
    assert not rep["edge_fragile"]
    assert "note_funding_fr" in rep

    # coûts énormes ⇒ edge fragile + avertissement FR
    gros_couts = [make_trade(10.0, fees=20.0, slippage=10.0, funding=5.0)]
    rep2 = cost_attribution(gros_couts, fallback_funding_used=False)
    assert rep2["edge_fragile"]
    assert "avertissement_fr" in rep2
