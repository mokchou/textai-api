"""Paper trading live (PRD §8) : même moteur, mêmes règles de fill que le
backtest — seule la source de données change (websocket Bybit).

`PaperRunner.process_candle()` est du code synchrone testable ; la boucle
websocket asyncio ne fait que l'alimenter.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

import numpy as np

from app.config.models import BotConfig
from app.db.connection import get_conn
from app.engine.feed import MarketData, MarketView, precompute
from app.engine.strategy import StrategyEngine
from app.engine.types import EngineState, Trade
from app.execution.simulator import ExecutionSimulator
from app.paper.aggregator import ContinuityGuard, LiveCandle
from app.paper.persistence import load_paper_state, save_paper_state

Broadcast = Callable[[str, dict[str, Any]], None]


class PaperRunner:
    """Une session de paper trading sur UNE paire."""

    def __init__(
        self,
        session_id: int,
        config: BotConfig,
        bootstrap: MarketData,
        fetch_missing: Callable[[int, int], list[LiveCandle]],
        broadcast: Broadcast | None = None,
    ) -> None:
        self.session_id = session_id
        self.config = config
        self.pending_config: BotConfig | None = None  # appliquée entre deux bougies
        self.md = bootstrap
        self.symbol = bootstrap.symbol
        self.tf_ms = bootstrap.tf_ms
        self.guard = ContinuityGuard(self.tf_ms, fetch_missing)
        if len(bootstrap.ts):
            self.guard.last_ts = int(bootstrap.ts[-1])
        self.broadcast = broadcast or (lambda ch, payload: None)
        self.trades: list[Trade] = []

        restored = load_paper_state(session_id)
        if restored is not None:
            self.state, _ = restored
        else:
            self.state = EngineState(equity=config.market.initial_equity)
        self._rebuild()

    # ------------------------------------------------------------------ #

    def _rebuild(self) -> None:
        """Reconstruit indicateurs/simulateur (au boot et à chaque changement de config)."""
        self.indicators = precompute(self.md, self.config)
        self.view = MarketView(self.md, self.indicators)
        self.engine = StrategyEngine(self.config)
        self.sim = ExecutionSimulator(self.config, self.md, self.indicators.exec_tf["atr"])

    def apply_config(self, new_config: BotConfig) -> None:
        """Demande un changement de paramètres — appliqué atomiquement avant la
        prochaine bougie (jamais au milieu d'un traitement)."""
        self.pending_config = new_config

    def _append(self, c: LiveCandle) -> int:
        self.md = MarketData(
            symbol=self.md.symbol,
            timeframe=self.md.timeframe,
            ts=np.append(self.md.ts, np.int64(c.ts)),
            open=np.append(self.md.open, c.open),
            high=np.append(self.md.high, c.high),
            low=np.append(self.md.low, c.low),
            close=np.append(self.md.close, c.close),
            volume=np.append(self.md.volume, c.volume),
            funding_rate_pct=np.append(
                self.md.funding_rate_pct,
                self.md.funding_rate_pct[-1] if len(self.md.funding_rate_pct) else np.nan,
            ),
            funding_event_rate_pct=np.append(
                self.md.funding_event_rate_pct,
                (self.md.funding_rate_pct[-1] if len(self.md.funding_rate_pct) else np.nan)
                if c.ts % (8 * 3600 * 1000) == 0
                else 0.0,
            ),
            oi=np.append(self.md.oi, self._latest_oi(c.ts)),
            basis_pct=np.append(self.md.basis_pct, np.nan),
        )
        return len(self.md) - 1

    def _latest_oi(self, ts: int) -> float:
        row = (
            get_conn()
            .execute(
                "SELECT open_interest FROM oi_collector WHERE symbol=? AND ts<=? "
                "ORDER BY ts DESC LIMIT 1",
                (self.symbol, ts),
            )
            .fetchone()
        )
        return float(row[0]) if row else float("nan")

    # ------------------------------------------------------------------ #

    def process_candle(self, candle: LiveCandle, replayed: bool = False) -> list[Trade]:
        """Traite une bougie CLOSE (et celles re-fetchées si trou détecté)."""
        closed_total: list[Trade] = []
        for c in self.guard.ingest(candle):
            if self.pending_config is not None:
                self.config = self.pending_config
                self.pending_config = None
                self._rebuild()
            i = self._append(c)
            self._rebuild()  # indicateurs recalculés sur l'historique étendu (causal)
            closed = self.sim.process_candle(self.state, i)
            self.view.set_index(i)
            _, record = self.engine.on_candle_close(self.view, self.state)
            self._persist(c, record, closed, replayed)
            closed_total.extend(closed)
            self._push_state(c)
        return closed_total

    # ------------------------------------------------------------------ #

    def _persist(self, c: LiveCandle, record: Any, closed: list[Trade], replayed: bool) -> None:
        conn = get_conn()
        if record.decisions or record.reasons_fr:
            evaluation = {
                "signals": record.signals,
                "filters": record.filters_passed,
                "reasons_fr": record.reasons_fr,
                "decisions": record.decisions,
                "replayed": replayed,
            }
            conn.execute(
                "INSERT INTO decision_journal(session_id, ts, symbol, state, evaluation_json, has_decision) "
                "VALUES (?,?,?,?,?,?)",
                (
                    self.session_id,
                    c.ts,
                    self.symbol,
                    record.state,
                    json.dumps(evaluation, ensure_ascii=False, default=str),
                    1 if record.decisions else 0,
                ),
            )
        for t in closed:
            self.trades.append(t)
            conn.execute(
                "INSERT INTO trades(paper_session_id, symbol, direction, mode, entry_ts, exit_ts, "
                "entry_price, exit_price, qty, exit_reason, aborted, pnl_gross, entry_fee, exit_fee, "
                "slippage_cost, funding_cost, pnl_net, r_multiple, mae, mfe, signals_json) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    self.session_id,
                    t.symbol,
                    t.direction.value,
                    t.mode.value,
                    t.entry_ts,
                    t.exit_ts,
                    t.entry_price,
                    t.exit_price,
                    t.qty,
                    t.exit_reason.value,
                    int(t.aborted),
                    t.pnl_gross,
                    t.entry_fee,
                    t.exit_fee,
                    t.slippage_cost,
                    t.funding_cost,
                    t.pnl_net,
                    t.r_multiple,
                    t.mae,
                    t.mfe,
                    json.dumps(t.entry_signals, ensure_ascii=False, default=str),
                ),
            )
            self.broadcast("paper:trade", t.to_json())
        conn.commit()
        save_paper_state(self.session_id, self.state, c.ts)

    def _push_state(self, c: LiveCandle) -> None:
        self.broadcast("paper:state", self.snapshot(last_price=c.close))

    def snapshot(self, last_price: float | None = None) -> dict[str, Any]:
        pos = self.state.position
        price = (
            last_price
            if last_price is not None
            else (float(self.md.close[-1]) if len(self.md) else None)
        )
        out: dict[str, Any] = {
            "session_id": self.session_id,
            "symbol": self.symbol,
            "ts": int(time.time() * 1000),
            "etat": self.state.state.value,
            "equite": self.state.equity,
            "kill_switch": self.state.killed,
            "kill_raison": self.state.kill_reason,
            "pertes_consecutives": self.state.consecutive_losses,
            "position": None,
            "ordres_en_attente": [
                {
                    "mode": p.mode.value,
                    "direction": p.direction.value,
                    "prix": p.price,
                    "suspendu": p.suspended,
                }
                for p in self.state.pending_entries
            ],
            "nb_trades": len(self.trades),
        }
        if pos is not None and price is not None:
            latent = (price - pos.entry_price) * pos.qty * pos.direction.sign
            out["position"] = {
                "direction": pos.direction.value,
                "mode": pos.mode.value,
                "qty": pos.qty,
                "prix_entree": pos.entry_price,
                "stop_courant": pos.stop_price,
                "pnl_latent": latent,
                "funding_cumule": pos.funding_paid,
                "trailing_actif": pos.trailing_active,
                "confirme": pos.confirmed,
            }
        return out

    def reset_kill_switch(self) -> None:
        self.state.killed = False
        self.state.kill_reason = None
        self.state.consecutive_losses = 0
        save_paper_state(self.session_id, self.state, self.guard.last_ts or 0)
        self.broadcast("paper:state", self.snapshot())
