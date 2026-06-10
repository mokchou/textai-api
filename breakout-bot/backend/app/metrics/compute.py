"""Métriques de performance (PRD §11) — calculées sur une liste de trades et
une courbe d'équité. Mêmes calculs pour backtest et période paper."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from app.engine.types import Trade

MS_PER_YEAR = 365.25 * 24 * 3600 * 1000


def compute_metrics(
    trades: list[Trade],
    equity_curve: np.ndarray,
    ts: np.ndarray,
    initial_equity: float,
) -> dict[str, Any]:
    n_trades = len(trades)
    out: dict[str, Any] = {
        "nb_trades": n_trades,
        "nb_avortes": sum(1 for t in trades if t.aborted),
    }
    pnl_net = sum(t.pnl_net for t in trades)
    pnl_gross = sum(t.pnl_gross for t in trades)
    out["pnl_net"] = pnl_net
    out["pnl_net_pct"] = pnl_net / initial_equity * 100.0 if initial_equity else 0.0
    out["pnl_brut"] = pnl_gross
    out["total_frais"] = sum(t.entry_fee + t.exit_fee for t in trades)
    out["total_slippage"] = sum(t.slippage_cost for t in trades)
    out["total_funding"] = sum(t.funding_cost for t in trades)

    if n_trades:
        wins = [t for t in trades if t.pnl_net > 0]
        losses = [t for t in trades if t.pnl_net <= 0]
        out["win_rate_pct"] = 100.0 * len(wins) / n_trades
        out["expectancy_r"] = float(np.mean([t.r_multiple for t in trades]))
        gains = sum(t.pnl_net for t in wins)
        pertes = abs(sum(t.pnl_net for t in losses))
        out["profit_factor"] = gains / pertes if pertes > 0 else math.inf if gains else 0.0
        out["mae_moyen_r"] = float(np.mean([t.mae for t in trades]))
        out["mfe_moyen_r"] = float(np.mean([t.mfe for t in trades]))
        # exposition : % du temps en position
        exposure = sum(t.exit_index - t.entry_index + 1 for t in trades)
        out["exposition_pct"] = 100.0 * exposure / max(len(equity_curve), 1)
    else:
        out.update(
            win_rate_pct=0.0,
            expectancy_r=0.0,
            profit_factor=0.0,
            mae_moyen_r=0.0,
            mfe_moyen_r=0.0,
            exposition_pct=0.0,
        )

    out.update(_drawdown(equity_curve, ts))
    out.update(_sharpe_sortino(trades, ts))
    return out


def _drawdown(equity: np.ndarray, ts: np.ndarray) -> dict[str, Any]:
    if len(equity) == 0:
        return {
            "max_drawdown": 0.0,
            "max_drawdown_pct": 0.0,
            "max_drawdown_duree_jours": 0.0,
            "max_drawdown_date": None,
        }
    peak = np.maximum.accumulate(equity)
    dd = peak - equity
    i_max = int(np.argmax(dd))
    with np.errstate(divide="ignore", invalid="ignore"):
        dd_pct = np.where(peak > 0, dd / peak * 100.0, 0.0)
    # durée : plus longue période sous le pic précédent
    under = equity < peak
    longest = cur = 0
    for u in under:
        cur = cur + 1 if u else 0
        longest = max(longest, cur)
    candle_ms = float(ts[1] - ts[0]) if len(ts) > 1 else 0.0
    return {
        "max_drawdown": float(dd[i_max]),
        "max_drawdown_pct": float(dd_pct[i_max]),
        "max_drawdown_duree_jours": longest * candle_ms / (24 * 3600 * 1000),
        "max_drawdown_date": int(ts[i_max]) if len(ts) else None,
    }


def _sharpe_sortino(trades: list[Trade], ts: np.ndarray) -> dict[str, Any]:
    """Sharpe/Sortino annualisés à la FRÉQUENCE RÉELLE des trades (PRD §11) :
    calculés sur les rendements par trade (R), annualisés par √(trades/an)."""
    if len(trades) < 2 or len(ts) < 2:
        return {"sharpe": 0.0, "sortino": 0.0, "trades_par_an": 0.0}
    r = np.array([t.r_multiple for t in trades])
    span_ms = float(ts[-1] - ts[0])
    trades_per_year = len(trades) * MS_PER_YEAR / span_ms if span_ms > 0 else 0.0
    ann = math.sqrt(trades_per_year) if trades_per_year > 0 else 0.0
    mean, std = float(r.mean()), float(r.std(ddof=1))
    sharpe = mean / std * ann if std > 0 else 0.0
    downside = r[r < 0]
    dstd = float(np.sqrt(np.mean(downside**2))) if len(downside) else 0.0
    sortino = mean / dstd * ann if dstd > 0 else (math.inf if mean > 0 else 0.0)
    return {
        "sharpe": sharpe,
        "sortino": sortino if math.isfinite(sortino) else 999.0,
        "trades_par_an": trades_per_year,
    }
