"""Test anti-look-ahead (PRD §7.2) — BLOQUANT en CI.

On tronque le dataset à T et on vérifie que les décisions émises jusqu'à T
sont identiques à celles du run complet : toute fuite du futur (indicateur
vectoriel mal borné, accès offset positif…) casse ce test.
"""

from __future__ import annotations

from app.backtest.runner import run_backtest
from tests.fixtures.candles import random_walk_market


def _serialize(decisions, up_to_index: int):
    return [d.to_json() for d in decisions if d.index < up_to_index]


def test_troncature_decisions_identiques(relaxed_config):
    md = random_walk_market(n=4000, seed=11)
    full = run_backtest(md, relaxed_config, journal="none")
    assert len(full.decisions) > 0, "le scénario doit générer de l'activité"

    for t in (1500, 2500, 3500):
        truncated = run_backtest(md.slice_to(t), relaxed_config, journal="none")
        assert _serialize(truncated.decisions, t) == _serialize(full.decisions, t), (
            f"divergence de décisions avant T={t} : fuite du futur probable"
        )


def test_troncature_trades_identiques(relaxed_config):
    md = random_walk_market(n=4000, seed=11)
    full = run_backtest(md, relaxed_config, journal="none")
    t = 3000
    truncated = run_backtest(md.slice_to(t), relaxed_config, journal="none")
    full_trades = [tr.to_json() for tr in full.trades if tr.exit_index < t]
    trunc_trades = [tr.to_json() for tr in truncated.trades if tr.exit_index < t]
    assert trunc_trades == full_trades
