"""Conteneurs de données de marché et vue causale `MarketView`.

`MarketView` est le SEUL objet par lequel le moteur accède aux données : il est
borné à l'index courant et lève sur tout accès au futur (`offset > 0`). C'est
la garantie structurelle anti-look-ahead, doublée du test CI de troncature.

Tout ici est pur (numpy en entrée, aucune I/O) : la construction depuis le
cache Parquet vit dans `app.data.feed`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.config.models import BotConfig
from app.engine import indicators as ind
from app.engine.range_detection import RangeScan, precompute_ranges
from app.engine.types import Candle, RangeZone

TF_MS = {"15m": 15 * 60 * 1000, "1h": 60 * 60 * 1000}


@dataclass(slots=True)
class MarketData:
    """Séries alignées sur le timeframe d'exécution (une paire)."""

    symbol: str
    timeframe: str
    ts: np.ndarray  # int64, epoch ms (ouverture)
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    # Dernier taux de funding publié (%, par 8 h) connu à la bougie i — NaN si inconnu.
    funding_rate_pct: np.ndarray = None  # type: ignore[assignment]
    # Taux appliqué si une échéance de funding (00/08/16 UTC) tombe dans la bougie i,
    # 0.0 sinon ; NaN ⇒ échéance présente mais taux historique manquant (fallback).
    funding_event_rate_pct: np.ndarray = None  # type: ignore[assignment]
    oi: np.ndarray = None  # type: ignore[assignment]
    basis_pct: np.ndarray = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        n = len(self.ts)
        if self.funding_rate_pct is None:
            self.funding_rate_pct = np.full(n, np.nan)
        if self.funding_event_rate_pct is None:
            self.funding_event_rate_pct = _default_funding_events(self.ts, self.tf_ms)
        if self.oi is None:
            self.oi = np.full(n, np.nan)
        if self.basis_pct is None:
            self.basis_pct = np.full(n, np.nan)

    @property
    def tf_ms(self) -> int:
        return TF_MS[self.timeframe]

    def __len__(self) -> int:
        return len(self.ts)

    def slice_to(self, end: int) -> MarketData:
        """Tronque les séries à `end` (exclu) — utilisé par le test anti-look-ahead."""
        return MarketData(
            symbol=self.symbol,
            timeframe=self.timeframe,
            ts=self.ts[:end],
            open=self.open[:end],
            high=self.high[:end],
            low=self.low[:end],
            close=self.close[:end],
            volume=self.volume[:end],
            funding_rate_pct=self.funding_rate_pct[:end],
            funding_event_rate_pct=self.funding_event_rate_pct[:end],
            oi=self.oi[:end],
            basis_pct=self.basis_pct[:end],
        )


def _default_funding_events(ts: np.ndarray, tf_ms: int) -> np.ndarray:
    """Échéances 00/08/16 UTC présentes dans chaque bougie, taux inconnu (NaN).

    Les bougies étant alignées sur le timeframe (qui divise 8 h), une échéance
    tombe dans la bougie ssi son ouverture est un multiple de 8 h.
    """
    out = np.zeros(len(ts))
    eight_h = 8 * 3600 * 1000
    out[(ts % eight_h) == 0] = np.nan
    return out


@dataclass(slots=True)
class HTFData:
    """Bougies agrégées du timeframe de range (K bougies d'exécution par bougie HTF)."""

    factor: int
    ts: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray


def build_htf(md: MarketData, factor: int) -> HTFData:
    n = (len(md) // factor) * factor
    shp = (-1, factor)
    return HTFData(
        factor=factor,
        ts=md.ts[:n].reshape(shp)[:, 0].copy(),
        open=md.open[:n].reshape(shp)[:, 0].copy(),
        high=md.high[:n].reshape(shp).max(axis=1),
        low=md.low[:n].reshape(shp).min(axis=1),
        close=md.close[:n].reshape(shp)[:, -1].copy(),
        volume=md.volume[:n].reshape(shp).sum(axis=1),
    )


@dataclass(slots=True)
class Indicators:
    """Indicateurs précalculés (fenêtres strictement causales)."""

    exec_tf: dict[str, np.ndarray]
    htf: HTFData
    ranges: RangeScan


def precompute(md: MarketData, config: BotConfig) -> Indicators:
    htf = build_htf(md, config.market.range_tf_multiple)
    atr_htf = ind.atr(htf.high, htf.low, htf.close, 14)
    bb_width = ind.bollinger_width(htf.close, 20)
    bb_rank = ind.rolling_percentile_rank(bb_width, config.range_detection.window)
    ranges = precompute_ranges(htf, atr_htf, bb_rank, config.range_detection)
    exec_tf = {
        "atr": ind.atr(md.high, md.low, md.close, 14),
        "adx": ind.adx(md.high, md.low, md.close, 14),
        "volume_rank": ind.rolling_percentile_rank(md.volume, config.entries.volume_window),
        "hurst": ind.hurst_rs(
            md.close, config.regime.hurst_window, config.regime.hurst_refresh_every
        ),
    }
    return Indicators(exec_tf=exec_tf, htf=htf, ranges=ranges)


class MarketView:
    """Vue causale sur les données : bornée à l'index courant `i`.

    Tout accès avec `offset > 0` (le futur) lève AssertionError.
    """

    __slots__ = ("md", "ind", "i")

    def __init__(self, md: MarketData, indicators: Indicators) -> None:
        self.md = md
        self.ind = indicators
        self.i = -1

    def set_index(self, i: int) -> None:
        assert 0 <= i < len(self.md)
        self.i = i

    def _at(self, offset: int) -> int:
        assert offset <= 0, "accès au futur interdit (anti-look-ahead)"
        j = self.i + offset
        assert j >= 0, "accès avant le début des données"
        return j

    def candle(self, offset: int = 0) -> Candle:
        j = self._at(offset)
        m = self.md
        return Candle(
            ts=int(m.ts[j]),
            open=float(m.open[j]),
            high=float(m.high[j]),
            low=float(m.low[j]),
            close=float(m.close[j]),
            volume=float(m.volume[j]),
        )

    def indicator(self, name: str, offset: int = 0) -> float:
        return float(self.ind.exec_tf[name][self._at(offset)])

    # ----- timeframe de range ------------------------------------------------

    def htf_index(self) -> int:
        """Index de la dernière bougie HTF entièrement clôturée à la clôture de i."""
        return (self.i + 1) // self.ind.htf.factor - 1

    def range_candidate(self) -> RangeZone | None:
        j = self.htf_index()
        if j < 0 or j >= len(self.ind.ranges.valid) or not self.ind.ranges.valid[j]:
            return None
        r = self.ind.ranges
        return RangeZone(
            low=float(r.low[j]),
            high=float(r.high[j]),
            touches_low=int(r.touches_low[j]),
            touches_high=int(r.touches_high[j]),
            detected_at_ts=int(self.ind.htf.ts[j]),
        )

    # ----- données crypto ----------------------------------------------------

    def funding_now(self) -> float:
        return float(self.md.funding_rate_pct[self.i])

    def oi_delta_pct(self) -> float:
        """Variation d'OI (%) sur la bougie courante ; NaN si données absentes."""
        i = self.i
        if i == 0:
            return float("nan")
        prev, cur = self.md.oi[i - 1], self.md.oi[i]
        if not (np.isfinite(prev) and np.isfinite(cur)) or prev <= 0:
            return float("nan")
        return float((cur - prev) / prev * 100.0)

    def basis_now(self) -> float:
        return float(self.md.basis_pct[self.i])
