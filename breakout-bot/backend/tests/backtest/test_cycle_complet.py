"""Intégration : le pipeline complet produit des trades cohérents sur un
marché synthétique, et l'état final est sérialisable (reprise à chaud)."""

from __future__ import annotations

import json

import pytest

from app.backtest.runner import run_backtest
from app.engine.types import EntryMode, ExitReason
from tests.fixtures.candles import random_walk_market


@pytest.fixture(scope="module")
def output():
    md = random_walk_market(n=6000, seed=3)
    from tests.conftest import make_relaxed_config

    return run_backtest(md, make_relaxed_config(), journal="interesting")


def test_des_trades_sont_generes(output):
    assert len(output.trades) > 0
    assert any(t.mode is EntryMode.MODE_1 for t in output.trades) or any(
        t.mode is EntryMode.MODE_2 for t in output.trades
    )


def test_decomposition_des_couts_coherente(output):
    for t in output.trades:
        assert t.pnl_net == pytest.approx(
            t.pnl_gross - t.entry_fee - t.exit_fee - t.slippage_cost - t.funding_cost
        )
        assert t.entry_fee >= 0 and t.exit_fee >= 0 and t.slippage_cost >= 0
        assert t.exit_index >= t.entry_index
        if t.exit_reason is ExitReason.AVORTE:
            assert t.aborted


def test_journal_de_decisions_alimente(output):
    assert len(output.journal) > 0
    refus = [r for r in output.journal if r.reasons_fr and not r.decisions]
    assert refus, "les setups refusés doivent être journalisés avec leur raison"


def test_etat_final_serialisable(output):
    payload = json.dumps(output.final_state.to_json(), ensure_ascii=False)
    assert "equity" in payload


def test_equite_suit_les_trades(output):
    from tests.conftest import make_relaxed_config

    cfg = make_relaxed_config()
    expected = cfg.market.initial_equity + sum(t.pnl_net for t in output.trades)
    assert output.final_state.equity == pytest.approx(expected)
