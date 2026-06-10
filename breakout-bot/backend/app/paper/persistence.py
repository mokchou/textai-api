"""Sérialisation/désérialisation de l'état moteur ⇒ reprise à chaud (PRD §8.4)."""

from __future__ import annotations

import json
import time
from typing import Any

from app.db.connection import get_conn
from app.engine.types import (
    Direction,
    EngineState,
    EntryMode,
    ExitReason,
    PendingEntry,
    Position,
    RangeZone,
    TradeState,
)


def state_to_json(state: EngineState) -> dict[str, Any]:
    return state.to_json()


def state_from_json(d: dict[str, Any]) -> EngineState:
    st = EngineState(
        state=TradeState(d["state"]),
        equity=d["equity"],
        consecutive_losses=d["consecutive_losses"],
        killed=d["killed"],
        kill_reason=d.get("kill_reason"),
        day_key=d.get("day_key"),
        day_start_equity=d.get("day_start_equity", 0.0),
        reached_1r_at=d.get("reached_1r_at"),
        breakout_index=d.get("breakout_index"),
    )
    if d.get("breakout_direction"):
        st.breakout_direction = Direction(d["breakout_direction"])
    if d.get("range_zone"):
        st.range_zone = RangeZone(**d["range_zone"])
    for p in d.get("pending_entries", []):
        st.pending_entries.append(
            PendingEntry(
                mode=EntryMode(p["mode"]),
                direction=Direction(p["direction"]),
                price=p["price"],
                placed_at_index=p["placed_at_index"],
                expires_after=p.get("expires_after"),
                suspended=p.get("suspended", False),
                entry_signals=p.get("entry_signals", {}),
            )
        )
    if d.get("position"):
        pos = dict(d["position"])
        pos["direction"] = Direction(pos["direction"])
        pos["mode"] = EntryMode(pos["mode"])
        if pos.get("exit_scheduled"):
            pos["exit_scheduled"] = ExitReason(pos["exit_scheduled"])
        st.position = Position(**pos)
    return st


def save_paper_state(session_id: int, state: EngineState, last_candle_ts: int) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO paper_state(session_id, engine_state_json, last_candle_ts, "
        "equity, updated_at) VALUES (?,?,?,?,?)",
        (
            session_id,
            json.dumps(state_to_json(state), ensure_ascii=False),
            last_candle_ts,
            state.equity,
            int(time.time() * 1000),
        ),
    )
    conn.commit()


def load_paper_state(session_id: int) -> tuple[EngineState, int] | None:
    row = (
        get_conn()
        .execute(
            "SELECT engine_state_json, last_candle_ts FROM paper_state WHERE session_id=?",
            (session_id,),
        )
        .fetchone()
    )
    if row is None:
        return None
    return state_from_json(json.loads(row["engine_state_json"])), int(row["last_candle_ts"])
