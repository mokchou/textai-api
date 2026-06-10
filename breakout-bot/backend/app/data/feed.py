"""Construction d'un `MarketData` (séries alignées) depuis un dataset Parquet.

Alignements :
- funding_rate_pct : dernier taux PUBLIÉ connu à chaque bougie (forward-fill,
  strictement causal — le taux de l'échéance T est connu à T) ;
- funding_event_rate_pct : taux appliqué aux bougies d'échéance (00/08/16 UTC),
  NaN si l'historique manque (⇒ taux de repli signalé) ;
- oi / basis : valeur à la bougie, forward-fill borné, NaN au-delà.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from app.engine.feed import MarketData

EIGHT_H_MS = 8 * 3600 * 1000


def _align_series(
    ts: np.ndarray, src_ts: np.ndarray, src_val: np.ndarray, max_staleness_ms: int
) -> np.ndarray:
    """Pour chaque bougie, dernière valeur source ≤ ts (causal), NaN si trop vieille."""
    out = np.full(len(ts), np.nan)
    if len(src_ts) == 0:
        return out
    idx = np.searchsorted(src_ts, ts, side="right") - 1
    valid = idx >= 0
    age = np.where(valid, ts - src_ts[np.clip(idx, 0, None)], np.inf)
    ok = valid & (age <= max_staleness_ms)
    out[ok] = src_val[idx[ok]]
    return out


def market_data_from_tables(tables: dict[str, pd.DataFrame], symbol: str, timeframe: str) -> MarketData:
    ohlcv = tables["ohlcv"].sort_values("ts").reset_index(drop=True)
    ts = ohlcv["ts"].to_numpy(np.int64)
    md = MarketData(
        symbol=symbol,
        timeframe=timeframe,
        ts=ts,
        open=ohlcv["open"].to_numpy(np.float64),
        high=ohlcv["high"].to_numpy(np.float64),
        low=ohlcv["low"].to_numpy(np.float64),
        close=ohlcv["close"].to_numpy(np.float64),
        volume=ohlcv["volume"].to_numpy(np.float64),
    )

    funding = tables.get("funding")
    if funding is not None and len(funding):
        f_ts = funding["ts"].to_numpy(np.int64)
        f_val = funding["rate_pct"].to_numpy(np.float64)
        md.funding_rate_pct = _align_series(ts, f_ts, f_val, max_staleness_ms=EIGHT_H_MS)
        # taux exact aux échéances : NaN si absent (⇒ repli signalé)
        events = (ts % EIGHT_H_MS) == 0
        rate_at = np.full(len(ts), 0.0)
        exact = {int(t): v for t, v in zip(f_ts, f_val, strict=True)}
        for i in np.where(events)[0]:
            rate_at[i] = exact.get(int(ts[i]), np.nan)
        md.funding_event_rate_pct = rate_at

    oi = tables.get("oi")
    if oi is not None and len(oi):
        md.oi = _align_series(
            ts,
            oi["ts"].to_numpy(np.int64),
            oi["open_interest"].to_numpy(np.float64),
            max_staleness_ms=4 * EIGHT_H_MS,
        )

    basis = tables.get("basis")
    if basis is not None and len(basis):
        md.basis_pct = _align_series(
            ts,
            basis["ts"].to_numpy(np.int64),
            basis["basis_pct"].to_numpy(np.float64),
            max_staleness_ms=EIGHT_H_MS,
        )
    return md


def load_market_data(path: Path) -> MarketData:
    from app.data.datasets import load_dataset

    tables, manifest = load_dataset(path)
    return market_data_from_tables(tables, manifest["symbol"], manifest["timeframe"])
