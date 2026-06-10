"""Détection de range sur le timeframe de range (PRD §5.2).

Précalculée par dataset+config : pour chaque bougie HTF j, la fenêtre
[j-W+1 .. j] est analysée — strictement causal. Un range est valide si :

1. ≥ N touches de chaque borne (tolérance de contact en % du prix) ;
2. compression de volatilité : largeur de Bollinger sous son percentile P_c ;
3. hauteur comprise entre min et max × ATR(HTF).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from app.config.models import RangeConfig

if TYPE_CHECKING:
    from app.engine.feed import HTFData


@dataclass(slots=True)
class RangeScan:
    """Résultat par bougie HTF : zone candidate et validité."""

    valid: np.ndarray  # bool
    low: np.ndarray
    high: np.ndarray
    touches_low: np.ndarray  # int
    touches_high: np.ndarray  # int


def precompute_ranges(
    htf: HTFData, atr_htf: np.ndarray, bb_rank: np.ndarray, cfg: RangeConfig
) -> RangeScan:
    n = len(htf.ts)
    w = cfg.window
    valid = np.zeros(n, dtype=bool)
    lo = np.full(n, np.nan)
    hi = np.full(n, np.nan)
    t_lo = np.zeros(n, dtype=np.int32)
    t_hi = np.zeros(n, dtype=np.int32)
    if n < w:
        return RangeScan(valid, lo, hi, t_lo, t_hi)

    highs = sliding_window_view(htf.high, w)  # fenêtre k couvre [k .. k+w-1]
    lows = sliding_window_view(htf.low, w)
    win_hi = highs.max(axis=1)
    win_lo = lows.min(axis=1)
    mid = (win_hi + win_lo) / 2.0
    tol = cfg.touch_tolerance_pct / 100.0 * mid

    touches_hi = (highs >= (win_hi - tol)[:, None]).sum(axis=1)
    touches_lo = (lows <= (win_lo + tol)[:, None]).sum(axis=1)

    idx = np.arange(w - 1, n)
    hi[idx] = win_hi
    lo[idx] = win_lo
    t_hi[idx] = touches_hi
    t_lo[idx] = touches_lo

    height = win_hi - win_lo
    atr_end = atr_htf[idx]
    rank_end = bb_rank[idx]
    with np.errstate(invalid="ignore"):
        ok = (
            (touches_hi >= cfg.min_touches)
            & (touches_lo >= cfg.min_touches)
            & (rank_end <= cfg.compression_percentile)
            & np.isfinite(atr_end)
            & (height >= cfg.height_min_atr * atr_end)
            & (height <= cfg.height_max_atr * atr_end)
        )
    valid[idx] = ok
    return RangeScan(valid, lo, hi, t_lo, t_hi)
