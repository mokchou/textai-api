"""Grid search, stabilité (optimum isolé) et walk-forward."""

from __future__ import annotations

import numpy as np
import pytest

from app.optimize.grid import GridParam, run_grid, set_param
from app.optimize.stability import stability_report
from app.optimize.walkforward import make_windows, run_walkforward
from tests.fixtures.candles import random_walk_market


def test_set_param_chemin_pointe(relaxed_config):
    set_param(relaxed_config, "regime.adx_min", 30.0)
    assert relaxed_config.regime.adx_min == 30.0


def test_stabilite_detecte_optimum_isole():
    # grille 1D : un pic isolé au milieu
    results = [
        {"params": {"x": v}, "expectancy_r": e}
        for v, e in [(1, 0.1), (2, 0.1), (3, 5.0), (4, 0.1), (5, 0.1)]
    ]
    rep = stability_report(results)
    assert rep["optimum_isole"]
    assert rep["score_plateau"] < 0.7
    assert "avertissement_fr" in rep
    assert rep["optimum"]["params"] == {"x": 3}


def test_stabilite_plateau_sain():
    results = [
        {"params": {"x": v}, "expectancy_r": e}
        for v, e in [(1, 0.8), (2, 1.0), (3, 1.1), (4, 1.0), (5, 0.9)]
    ]
    rep = stability_report(results)
    assert not rep["optimum_isole"]
    assert rep["score_plateau"] >= 0.7


def test_stabilite_heatmap_2d():
    results = [
        {"params": {"x": x, "y": y}, "expectancy_r": float(x + y)}
        for x in (1, 2, 3)
        for y in (10, 20)
    ]
    rep = stability_report(results)
    assert np.array(rep["heatmap"]).shape == (3, 2)
    assert rep["optimum"]["params"] == {"x": 3, "y": 20}


def test_fenetres_walkforward():
    day = 86_400_000
    ts = np.arange(0, 400 * day, 900_000, dtype=np.int64)
    windows = make_windows(ts, train_days=180, test_days=60)
    assert len(windows) >= 2
    for w in windows:
        assert w.train_end == w.test_start
        assert w.test_end - w.test_start == 60 * day
    # glissement d'une fenêtre test
    assert windows[1].train_start - windows[0].train_start == 60 * day


@pytest.mark.slow
def test_grid_et_walkforward_de_bout_en_bout(relaxed_config):
    md = random_walk_market(n=96 * 300, seed=9)  # ~300 jours
    params = [GridParam(path="regime.adx_min", values=(15.0, 20.0))]
    results = run_grid(md, relaxed_config, params, max_workers=2)
    assert len(results) == 2
    assert {r["params"]["regime.adx_min"] for r in results} == {15.0, 20.0}

    wf = run_walkforward(md, relaxed_config, params, train_days=120, test_days=60, max_workers=2)
    assert wf["nb_fenetres"] >= 1
    assert "metriques_agregees_test" in wf
    assert wf["derniers_params"] is not None
