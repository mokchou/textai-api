"""Gestion des sessions de paper trading : démarrage, arrêt, reprise à chaud.

Les index du moteur sont des positions absolues depuis `bootstrap_start_ts`
(fixé à la création de la session) : ils restent valides entre deux
redémarrages, ce qui rend la reprise à chaud triviale.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import numpy as np

from app.config.models import BotConfig
from app.data.exchange import TF_MS, BybitAdapter
from app.db.connection import get_conn
from app.engine.feed import MarketData
from app.paper.aggregator import LiveCandle
from app.paper.alerts import send_alert
from app.paper.runner import Broadcast, PaperRunner
from app.paper.ws_client import confirmed_klines

log = logging.getLogger(__name__)

BOOTSTRAP_DAYS = 30  # chauffe des indicateurs (Hurst 100 bougies HTF incluses)


def _rows_to_candles(rows: list[list[float]]) -> list[LiveCandle]:
    return [
        LiveCandle(ts=int(r[0]), open=r[1], high=r[2], low=r[3], close=r[4], volume=r[5])
        for r in rows
    ]


class PaperManager:
    def __init__(self, broadcast: Broadcast) -> None:
        self.broadcast = broadcast
        self.runners: dict[int, PaperRunner] = {}
        self.tasks: dict[int, asyncio.Task] = {}
        self.adapter: BybitAdapter | None = None

    def _get_adapter(self) -> BybitAdapter:
        if self.adapter is None:
            self.adapter = BybitAdapter()
        return self.adapter

    # ------------------------------------------------------------------ #

    async def start(self, symbol: str, config: BotConfig) -> int:
        now = int(time.time() * 1000)
        tf = config.market.timeframe
        bootstrap_start = ((now - BOOTSTRAP_DAYS * 86_400_000) // (8 * 3600 * 1000)) * (
            8 * 3600 * 1000
        )
        conn = get_conn()
        cur = conn.execute(
            "INSERT INTO paper_sessions(config_json, symbol, timeframe, bootstrap_start_ts, "
            "started_at, status) VALUES (?,?,?,?,?, 'active')",
            (config.model_dump_json(), symbol, tf, bootstrap_start, now),
        )
        conn.commit()
        session_id = int(cur.lastrowid)
        await self._launch(session_id, symbol, tf, bootstrap_start, config, resume=False)
        send_alert(f"📈 Paper trading démarré : {symbol} {tf} (session {session_id})")
        return session_id

    async def resume_active_sessions(self) -> None:
        rows = get_conn().execute("SELECT * FROM paper_sessions WHERE status='active'").fetchall()
        for row in rows:
            try:
                await self._launch(
                    int(row["id"]),
                    row["symbol"],
                    row["timeframe"],
                    int(row["bootstrap_start_ts"]),
                    BotConfig.model_validate(json.loads(row["config_json"])),
                    resume=True,
                )
                log.info("session paper %s reprise à chaud", row["id"])
            except Exception as exc:
                log.error("reprise de la session %s impossible : %s", row["id"], exc)

    async def _launch(
        self,
        session_id: int,
        symbol: str,
        tf: str,
        bootstrap_start: int,
        config: BotConfig,
        resume: bool,
    ) -> None:
        adapter = self._get_adapter()
        loop = asyncio.get_running_loop()
        now = int(time.time() * 1000)

        rows = await loop.run_in_executor(
            None, adapter.fetch_ohlcv, symbol, tf, bootstrap_start, now
        )
        candles = _rows_to_candles(rows)
        if not candles:
            raise RuntimeError(f"aucune bougie REST pour {symbol} {tf}")

        from app.paper.persistence import load_paper_state

        restored = load_paper_state(session_id) if resume else None
        cut_ts = restored[1] if restored else candles[-1].ts
        boot = [c for c in candles if c.ts <= cut_ts]
        to_replay = [c for c in candles if c.ts > cut_ts]

        md = MarketData(
            symbol=symbol,
            timeframe=tf,
            ts=np.array([c.ts for c in boot], dtype=np.int64),
            open=np.array([c.open for c in boot]),
            high=np.array([c.high for c in boot]),
            low=np.array([c.low for c in boot]),
            close=np.array([c.close for c in boot]),
            volume=np.array([c.volume for c in boot]),
        )

        def fetch_missing(start_ms: int, end_ms: int) -> list[LiveCandle]:
            return _rows_to_candles(adapter.fetch_ohlcv(symbol, tf, start_ms, end_ms))

        runner = PaperRunner(session_id, config, md, fetch_missing, self.broadcast)
        self.runners[session_id] = runner

        # rejeu silencieux des bougies manquées pendant l'arrêt (marquées replayed)
        for c in to_replay:
            await loop.run_in_executor(None, runner.process_candle, c, True)

        self.tasks[session_id] = asyncio.create_task(
            self._consume(session_id, symbol, tf), name=f"paper-{session_id}"
        )

    async def _consume(self, session_id: int, symbol: str, tf: str) -> None:
        runner = self.runners[session_id]
        loop = asyncio.get_running_loop()
        try:
            async for candle in confirmed_klines(symbol, tf):
                killed_before = runner.state.killed
                trades = await loop.run_in_executor(None, runner.process_candle, candle)
                for t in trades:
                    send_alert(
                        f"{'🟢' if t.pnl_net >= 0 else '🔴'} {symbol} {t.direction.value} "
                        f"{t.mode.value} clos ({t.exit_reason.value}) : "
                        f"{t.pnl_net:+.2f} USDT ({t.r_multiple:+.2f} R)"
                    )
                if runner.state.killed and not killed_before:
                    send_alert(
                        f"⛔ Kill switch déclenché sur {symbol} : {runner.state.kill_reason}"
                    )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.error("session paper %s arrêtée sur erreur : %s", session_id, exc)

    # ------------------------------------------------------------------ #

    async def stop(self, session_id: int) -> None:
        task = self.tasks.pop(session_id, None)
        if task is not None:
            task.cancel()
        self.runners.pop(session_id, None)
        conn = get_conn()
        conn.execute(
            "UPDATE paper_sessions SET status='arretee', stopped_at=? WHERE id=?",
            (int(time.time() * 1000), session_id),
        )
        conn.commit()

    async def stop_all(self) -> None:
        for sid in list(self.tasks):
            await self.stop(sid)

    def any_position_open(self) -> bool:
        return any(r.state.position is not None for r in self.runners.values())

    def apply_config(self, config: BotConfig) -> None:
        for runner in self.runners.values():
            runner.apply_config(config)

    def snapshots(self) -> list[dict[str, Any]]:
        return [r.snapshot() for r in self.runners.values()]

    # ------------------------------------------------------------------ #

    def collect_oi(self) -> None:
        """Collecte continue d'open interest (toutes les 5 min, dès P0)."""
        adapter = self._get_adapter()
        symbols = {r.symbol for r in self.runners.values()}
        from app.api.deps import load_active_config

        symbols.update(load_active_config().market.symbols)
        from app.data.store import record_oi_snapshot

        for symbol in symbols:
            try:
                now = int(time.time() * 1000)
                rows = adapter.fetch_open_interest(symbol, "15m", now - 3600_000, now)
                if rows:
                    ts, oi = rows[-1]
                    record_oi_snapshot(symbol, ts, oi)
            except Exception as exc:
                log.debug("collecte OI %s échouée : %s", symbol, exc)


TF = TF_MS  # ré-export pratique
