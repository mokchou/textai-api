"""Constructeurs de bougies et de données de marché synthétiques pour les tests.

Toutes les suites d'exécution (table 6.4), de moteur et de backtest s'appuient
sur ces fixtures : des bougies construites À LA MAIN, aux valeurs exactes.
"""

from __future__ import annotations

import numpy as np

from app.engine.feed import MarketData

TF_15M_MS = 15 * 60 * 1000
T0 = 1_700_006_400_000  # 2023-11-15 00:00:00 UTC — multiple de 8 h


def make_market(
    candles: list[tuple[float, float, float, float, float]],
    symbol: str = "TESTUSDT",
    timeframe: str = "15m",
    t0: int = T0,
    funding_rate_pct: float | None = None,
    oi: list[float] | None = None,
    basis_pct: float | None = None,
) -> MarketData:
    """candles = liste de tuples (open, high, low, close, volume)."""
    n = len(candles)
    arr = np.array(candles, dtype=float)
    ts = (t0 + np.arange(n, dtype=np.int64) * TF_15M_MS).astype(np.int64)
    md = MarketData(
        symbol=symbol,
        timeframe=timeframe,
        ts=ts,
        open=arr[:, 0].copy(),
        high=arr[:, 1].copy(),
        low=arr[:, 2].copy(),
        close=arr[:, 3].copy(),
        volume=arr[:, 4].copy(),
    )
    if funding_rate_pct is not None:
        md.funding_rate_pct = np.full(n, funding_rate_pct)
        events = np.isnan(md.funding_event_rate_pct)
        md.funding_event_rate_pct = np.where(events, funding_rate_pct, 0.0)
    if oi is not None:
        md.oi = np.array(oi, dtype=float)
    if basis_pct is not None:
        md.basis_pct = np.full(n, basis_pct)
    return md


def random_walk_market(
    n: int = 6000,
    seed: int = 7,
    start_price: float = 100.0,
    symbol: str = "RNDUSDT",
) -> MarketData:
    """Marché synthétique réaliste : marche aléatoire avec phases de compression
    (ranges) et d'expansion, pics de volume sur les grandes bougies. Utilisé par
    les tests anti-look-ahead, de reproductibilité et de performance."""
    rng = np.random.default_rng(seed)
    # volatilité par régime : blocs alternés calmes/agités
    block = 240
    n_blocks = n // block + 1
    vol_levels = rng.choice([0.0006, 0.0012, 0.0030], size=n_blocks, p=[0.45, 0.35, 0.20])
    sigma = np.repeat(vol_levels, block)[:n]
    drift = np.repeat(rng.normal(0, 0.0004, n_blocks), block)[:n]
    rets = rng.normal(drift, sigma)
    close = start_price * np.exp(np.cumsum(rets))
    open_ = np.empty(n)
    open_[0] = start_price
    open_[1:] = close[:-1]
    span = np.abs(rets) * close * rng.uniform(0.5, 1.5, n) + close * sigma * 0.5
    high = np.maximum(open_, close) + span * rng.uniform(0.1, 0.6, n)
    low = np.minimum(open_, close) - span * rng.uniform(0.1, 0.6, n)
    volume = rng.lognormal(0, 0.5, n) * 100.0 * (1.0 + 8.0 * (np.abs(rets) / (sigma + 1e-9)))

    ts = (T0 + np.arange(n, dtype=np.int64) * TF_15M_MS).astype(np.int64)
    md = MarketData(
        symbol=symbol,
        timeframe="15m",
        ts=ts,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )
    md.funding_rate_pct = np.full(n, 0.01)
    md.funding_event_rate_pct = np.where(np.isnan(md.funding_event_rate_pct), 0.01, 0.0)
    oi = 1e6 * np.exp(np.cumsum(rng.normal(0, 0.004, n)))
    md.oi = oi
    md.basis_pct = rng.normal(0, 0.05, n)
    return md
