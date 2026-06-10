"""Assemblage du rapport de backtest : run_id reproductible + métriques
complètes + attribution des coûts + ventilations."""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from app.backtest.runner import BacktestOutput
from app.config.hashing import config_hash
from app.config.models import BotConfig
from app.engine.feed import MarketData
from app.engine.version import ENGINE_VERSION
from app.metrics.breakdowns import compute_breakdowns
from app.metrics.compute import compute_metrics
from app.metrics.cost_attribution import cost_attribution


def make_run_id(dataset_hash: str, cfg: BotConfig) -> str:
    payload = f"{dataset_hash}:{config_hash(cfg)}:{ENGINE_VERSION}"
    return hashlib.sha256(payload.encode()).hexdigest()


def build_report(
    output: BacktestOutput,
    md: MarketData,
    cfg: BotConfig,
    dataset_hash: str,
) -> dict[str, Any]:
    init_eq = cfg.market.initial_equity
    metrics = compute_metrics(output.trades, output.equity_curve, md.ts, init_eq)
    return {
        "run_id": make_run_id(dataset_hash, cfg),
        "engine_version": ENGINE_VERSION,
        "dataset_hash": dataset_hash,
        "config_hash": config_hash(cfg),
        "symbol": md.symbol,
        "timeframe": md.timeframe,
        "periode": {"debut_ts": int(md.ts[0]), "fin_ts": int(md.ts[-1])} if len(md.ts) else None,
        "metriques": metrics,
        "ventilations": compute_breakdowns(output.trades, output.equity_curve, md.ts, init_eq),
        "attribution_couts": cost_attribution(output.trades, output.fallback_funding_used),
        "trades": [t.to_json() for t in output.trades],
        "kill_switch_final": output.final_state.killed,
    }


def equity_series(output: BacktestOutput, md: MarketData, max_points: int = 2000) -> list[dict]:
    """Courbe d'équité sous-échantillonnée pour l'UI (Recharts)."""
    n = len(output.equity_curve)
    if n == 0:
        return []
    step = max(1, n // max_points)
    idx = np.arange(0, n, step)
    if idx[-1] != n - 1:
        idx = np.append(idx, n - 1)
    peak = np.maximum.accumulate(output.equity_curve)
    dd = output.equity_curve - peak
    return [
        {
            "ts": int(md.ts[i]),
            "equite": float(output.equity_curve[i]),
            "drawdown": float(dd[i]),
        }
        for i in idx
    ]
