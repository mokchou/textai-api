"""Critère CU1 (PRD §7.7) : 12 mois × 3 paires en M15 < 60 s."""

from __future__ import annotations

import time

import pytest

from app.backtest.runner import run_backtest
from tests.fixtures.candles import random_walk_market

CANDLES_12_MONTHS_M15 = 365 * 96  # ≈ 35 040


@pytest.mark.slow
def test_12_mois_3_paires_m15_sous_60s(relaxed_config):
    markets = [
        random_walk_market(n=CANDLES_12_MONTHS_M15, seed=s, symbol=f"PAIRE{s}") for s in (1, 2, 3)
    ]
    start = time.perf_counter()
    for md in markets:
        run_backtest(md, relaxed_config, journal="interesting")
    elapsed = time.perf_counter() - start
    assert elapsed < 60.0, f"backtest trop lent : {elapsed:.1f} s ≥ 60 s"
