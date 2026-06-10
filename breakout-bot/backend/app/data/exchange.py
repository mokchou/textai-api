"""Adaptateur d'exchange — Bybit en v1, swappable via le protocole.

OHLCV et funding passent par CCXT ; l'open interest et les klines d'index/mark
(pour le basis) passent par l'API native Bybit v5, non couverte uniformément
par CCXT.
"""

from __future__ import annotations

import time
from typing import Any, Protocol

import httpx

BYBIT_BASE = "https://api.bybit.com"
TF_TO_CCXT = {"15m": "15m", "1h": "1h"}
TF_TO_BYBIT_INTERVAL = {"15m": "15", "1h": "60"}
TF_TO_BYBIT_OI = {"15m": "15min", "1h": "1h"}
TF_MS = {"15m": 15 * 60 * 1000, "1h": 60 * 60 * 1000}


class ExchangeAdapter(Protocol):
    """Contrat minimal : listes de lignes [ts_ms, ...] triées par ts croissant."""

    def fetch_ohlcv(self, symbol: str, timeframe: str, start_ms: int, end_ms: int) -> list[list[float]]: ...

    def fetch_funding_history(self, symbol: str, start_ms: int, end_ms: int) -> list[tuple[int, float]]: ...

    def fetch_open_interest(self, symbol: str, timeframe: str, start_ms: int, end_ms: int) -> list[tuple[int, float]]: ...

    def fetch_basis(self, symbol: str, timeframe: str, start_ms: int, end_ms: int) -> list[tuple[int, float]]: ...


class BybitAdapter:
    def __init__(self, rate_limit_s: float = 0.15) -> None:
        import ccxt

        self.ccxt = ccxt.bybit({"options": {"defaultType": "swap"}})
        self.http = httpx.Client(base_url=BYBIT_BASE, timeout=30.0)
        self.rate_limit_s = rate_limit_s

    def _pause(self) -> None:
        time.sleep(self.rate_limit_s)

    # ------------------------------------------------------------------ #

    def fetch_ohlcv(
        self, symbol: str, timeframe: str, start_ms: int, end_ms: int
    ) -> list[list[float]]:
        market = f"{symbol[:-4]}/USDT:USDT" if symbol.endswith("USDT") else symbol
        tf = TF_TO_CCXT[timeframe]
        out: list[list[float]] = []
        since = start_ms
        while since < end_ms:
            batch = self.ccxt.fetch_ohlcv(market, tf, since=since, limit=1000)
            if not batch:
                break
            out.extend(row for row in batch if row[0] < end_ms)
            last = batch[-1][0]
            if last <= since:
                break
            since = last + TF_MS[timeframe]
            self._pause()
        return _dedupe_sorted(out)

    def fetch_funding_history(
        self, symbol: str, start_ms: int, end_ms: int
    ) -> list[tuple[int, float]]:
        market = f"{symbol[:-4]}/USDT:USDT" if symbol.endswith("USDT") else symbol
        out: list[tuple[int, float]] = []
        since = start_ms
        while since < end_ms:
            batch = self.ccxt.fetch_funding_rate_history(market, since=since, limit=200)
            if not batch:
                break
            for row in batch:
                ts = int(row["timestamp"])
                if ts < end_ms:
                    out.append((ts, float(row["fundingRate"]) * 100.0))  # en %/8 h
            last = int(batch[-1]["timestamp"])
            if last <= since:
                break
            since = last + 1
            self._pause()
        return sorted(dict(out).items())

    def fetch_open_interest(
        self, symbol: str, timeframe: str, start_ms: int, end_ms: int
    ) -> list[tuple[int, float]]:
        out: dict[int, float] = {}
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {
                "category": "linear",
                "symbol": symbol,
                "intervalTime": TF_TO_BYBIT_OI[timeframe],
                "startTime": start_ms,
                "endTime": end_ms,
                "limit": 200,
            }
            if cursor:
                params["cursor"] = cursor
            data = self._get("/v5/market/open-interest", params)
            rows = data.get("list", [])
            for r in rows:
                out[int(r["timestamp"])] = float(r["openInterest"])
            cursor = data.get("nextPageCursor") or None
            if not rows or not cursor:
                break
            self._pause()
        return sorted(out.items())

    def fetch_basis(
        self, symbol: str, timeframe: str, start_ms: int, end_ms: int
    ) -> list[tuple[int, float]]:
        """Basis %, par bougie : (mark − index) / index, sur les clôtures."""
        mark = self._fetch_kline("/v5/market/mark-price-kline", symbol, timeframe, start_ms, end_ms)
        index = self._fetch_kline("/v5/market/index-price-kline", symbol, timeframe, start_ms, end_ms)
        out: list[tuple[int, float]] = []
        for ts, m_close in mark.items():
            i_close = index.get(ts)
            if i_close:
                out.append((ts, (m_close - i_close) / i_close * 100.0))
        return sorted(out)

    # ------------------------------------------------------------------ #

    def _fetch_kline(
        self, path: str, symbol: str, timeframe: str, start_ms: int, end_ms: int
    ) -> dict[int, float]:
        out: dict[int, float] = {}
        start = start_ms
        tf_ms = TF_MS[timeframe]
        while start < end_ms:
            data = self._get(
                path,
                {
                    "category": "linear",
                    "symbol": symbol,
                    "interval": TF_TO_BYBIT_INTERVAL[timeframe],
                    "start": start,
                    "end": end_ms,
                    "limit": 1000,
                },
            )
            rows = data.get("list", [])
            if not rows:
                break
            for r in rows:  # [ts, open, high, low, close]
                out[int(r[0])] = float(r[4])
            oldest = min(int(r[0]) for r in rows)
            newest = max(int(r[0]) for r in rows)
            if newest + tf_ms >= end_ms and oldest <= start:
                break
            start = newest + tf_ms
            self._pause()
        return out

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        resp = self.http.get(path, params=params)
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("retCode") != 0:
            raise RuntimeError(f"Bybit {path} : {payload.get('retMsg')}")
        return payload["result"]


def _dedupe_sorted(rows: list[list[float]]) -> list[list[float]]:
    seen: dict[int, list[float]] = {}
    for r in rows:
        seen[int(r[0])] = r
    return [seen[k] for k in sorted(seen)]
