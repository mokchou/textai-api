"""Reproductibilité (PRD §7.4) : même triplet (dataset, config, moteur)
⇒ résultat bit à bit identique."""

from __future__ import annotations

import json

import numpy as np

from app.backtest.runner import run_backtest
from app.config.hashing import canonical_json, config_hash
from tests.fixtures.candles import random_walk_market


def test_deux_runs_identiques_bit_a_bit(relaxed_config):
    md = random_walk_market(n=3000, seed=5)
    r1 = run_backtest(md, relaxed_config, journal="none")
    r2 = run_backtest(md, relaxed_config, journal="none")

    j1 = canonical_json([d.to_json() for d in r1.decisions])
    j2 = canonical_json([d.to_json() for d in r2.decisions])
    assert j1 == j2

    t1 = canonical_json([t.to_json() for t in r1.trades])
    t2 = canonical_json([t.to_json() for t in r2.trades])
    assert t1 == t2

    assert np.array_equal(r1.equity_curve, r2.equity_curve)


def test_config_hash_stable_et_sensible(relaxed_config, default_config):
    h1 = config_hash(relaxed_config)
    h2 = config_hash(relaxed_config.model_copy(deep=True))
    assert h1 == h2
    assert h1 != config_hash(default_config)
    # le hash canonique ne dépend pas de l'ordre des clés
    d = relaxed_config.model_dump(mode="json")
    assert canonical_json(d) == canonical_json(json.loads(canonical_json(d)))
