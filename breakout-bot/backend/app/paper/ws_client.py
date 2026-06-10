"""Client websocket public Bybit v5 : klines confirmées, reconnexion
automatique avec backoff exponentiel."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

import websockets

from app.paper.aggregator import LiveCandle

log = logging.getLogger(__name__)

BYBIT_WS_LINEAR = "wss://stream.bybit.com/v5/public/linear"
TF_TO_WS_INTERVAL = {"15m": "15", "1h": "60"}


async def confirmed_klines(
    symbol: str, timeframe: str, url: str = BYBIT_WS_LINEAR
) -> AsyncIterator[LiveCandle]:
    """Itère les bougies CLOSES (confirm=true) du flux kline Bybit."""
    topic = f"kline.{TF_TO_WS_INTERVAL[timeframe]}.{symbol}"
    backoff = 1.0
    while True:
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                await ws.send(json.dumps({"op": "subscribe", "args": [topic]}))
                backoff = 1.0
                async for raw in ws:
                    msg = json.loads(raw)
                    for k in msg.get("data", []) or []:
                        if isinstance(k, dict) and k.get("confirm"):
                            yield LiveCandle(
                                ts=int(k["start"]),
                                open=float(k["open"]),
                                high=float(k["high"]),
                                low=float(k["low"]),
                                close=float(k["close"]),
                                volume=float(k["volume"]),
                            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning(
                "websocket %s déconnecté (%s) — reconnexion dans %.0f s", topic, exc, backoff
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60.0)
