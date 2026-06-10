"""Walk-forward (PRD §7.5) : fenêtres train/test glissantes, paramètres figés
sur le test, métriques finales agrégées sur les fenêtres test UNIQUEMENT."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from app.backtest.runner import run_backtest
from app.config.models import BotConfig
from app.engine.feed import MarketData
from app.engine.types import Trade
from app.metrics.compute import compute_metrics
from app.optimize.grid import GridParam, run_grid, set_param
from app.optimize.stability import stability_report

DAY_MS = 24 * 3600 * 1000


@dataclass(slots=True)
class WalkForwardWindow:
    train_start: int
    train_end: int
    test_start: int
    test_end: int


def make_windows(
    ts: np.ndarray, train_days: int = 180, test_days: int = 60
) -> list[WalkForwardWindow]:
    start, end = int(ts[0]), int(ts[-1])
    train_ms, test_ms = train_days * DAY_MS, test_days * DAY_MS
    windows = []
    cursor = start
    while cursor + train_ms + test_ms <= end + DAY_MS:
        windows.append(
            WalkForwardWindow(
                train_start=cursor,
                train_end=cursor + train_ms,
                test_start=cursor + train_ms,
                test_end=cursor + train_ms + test_ms,
            )
        )
        cursor += test_ms  # glissement d'une fenêtre test
    return windows


def _slice_md(md: MarketData, start: int, end: int) -> MarketData:
    i0 = int(np.searchsorted(md.ts, start, side="left"))
    i1 = int(np.searchsorted(md.ts, end, side="left"))
    sl = md.slice_to(i1)
    # re-tronque le début en conservant l'alignement 8 h (start aligné par construction)
    return MarketData(
        symbol=sl.symbol,
        timeframe=sl.timeframe,
        ts=sl.ts[i0:],
        open=sl.open[i0:],
        high=sl.high[i0:],
        low=sl.low[i0:],
        close=sl.close[i0:],
        volume=sl.volume[i0:],
        funding_rate_pct=sl.funding_rate_pct[i0:],
        funding_event_rate_pct=sl.funding_event_rate_pct[i0:],
        oi=sl.oi[i0:],
        basis_pct=sl.basis_pct[i0:],
    )


def run_walkforward(
    md: MarketData,
    base_config: BotConfig,
    params: list[GridParam],
    train_days: int = 180,
    test_days: int = 60,
    max_workers: int = 4,
    metric: str = "expectancy_r",
    progress_cb: Any = None,
) -> dict[str, Any]:
    windows = make_windows(md.ts, train_days, test_days)
    if not windows:
        raise ValueError(
            "Période trop courte pour le walk-forward : il faut au moins "
            f"{train_days + test_days} jours de données."
        )

    per_window: list[dict[str, Any]] = []
    test_trades: list[Trade] = []
    test_equity: list[np.ndarray] = []
    test_ts: list[np.ndarray] = []

    for w_idx, w in enumerate(windows):
        train_md = _slice_md(md, w.train_start, w.train_end)
        grid_results = run_grid(train_md, base_config, params, max_workers=max_workers)
        stab = stability_report(grid_results, metric=metric)
        best_params = stab["optimum"]["params"]

        cfg = base_config.model_copy(deep=True)
        for path, value in best_params.items():
            set_param(cfg, path, value)
        cfg = BotConfig.model_validate(cfg.model_dump())

        test_md = _slice_md(md, w.test_start, w.test_end)
        out = run_backtest(test_md, cfg, journal="none")
        m = compute_metrics(out.trades, out.equity_curve, test_md.ts, cfg.market.initial_equity)
        per_window.append(
            {
                "fenetre": {
                    "train": [w.train_start, w.train_end],
                    "test": [w.test_start, w.test_end],
                },
                "params_retenus": best_params,
                "score_plateau": stab["score_plateau"],
                "optimum_isole": stab["optimum_isole"],
                "metriques_test": m,
            }
        )
        test_trades.extend(out.trades)
        test_equity.append(out.equity_curve)
        test_ts.append(test_md.ts)
        if progress_cb is not None:
            progress_cb(w_idx + 1, len(windows))

    agg_equity = np.concatenate(test_equity) if test_equity else np.array([])
    agg_ts = np.concatenate(test_ts) if test_ts else np.array([])
    agg = compute_metrics(test_trades, agg_equity, agg_ts, base_config.market.initial_equity)
    return {
        "fenetres": per_window,
        "metriques_agregees_test": agg,
        "nb_fenetres": len(windows),
        "params_balayes": [p.path for p in params],
        "derniers_params": per_window[-1]["params_retenus"] if per_window else None,
        "stabilite_derniere_fenetre": per_window[-1]["score_plateau"] if per_window else None,
    }
