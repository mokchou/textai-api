"""Paper trading : démarrer/arrêter, état live, journal de décisions,
kill switch, rapport de cohérence backtest/paper."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import load_active_config
from app.backtest.runner import run_backtest
from app.config.models import BotConfig
from app.db.connection import get_conn
from app.engine.types import Direction, EntryMode, ExitReason, Trade
from app.paper.coherence import coherence_report
from app.paper.manager import PaperManager

router = APIRouter(prefix="/api/paper", tags=["paper trading"])


def _manager(request: Request) -> PaperManager:
    mgr = getattr(request.app.state, "paper_manager", None)
    if mgr is None:
        raise HTTPException(503, "gestionnaire de paper trading non initialisé")
    return mgr


class StartRequest(BaseModel):
    symbol: str | None = None  # défaut : première paire de la config active
    config: dict[str, Any] | None = None


@router.post("/start")
async def start(req: StartRequest, request: Request) -> dict[str, Any]:
    cfg = BotConfig.model_validate(req.config) if req.config else load_active_config()
    symbol = req.symbol or cfg.market.symbols[0]
    session_id = await _manager(request).start(symbol, cfg)
    return {"session_id": session_id}


@router.post("/stop/{session_id}")
async def stop(session_id: int, request: Request) -> dict[str, Any]:
    await _manager(request).stop(session_id)
    return {"ok": True}


@router.get("/state")
def state(request: Request) -> dict[str, Any]:
    return {"sessions": _manager(request).snapshots()}


@router.get("/journal")
def journal(session_id: int | None = None, limit: int = 200) -> list[dict[str, Any]]:
    q = "SELECT * FROM decision_journal"
    args: tuple = ()
    if session_id is not None:
        q += " WHERE session_id=?"
        args = (session_id,)
    q += " ORDER BY ts DESC LIMIT ?"
    rows = get_conn().execute(q, (*args, limit)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["evaluation"] = json.loads(d.pop("evaluation_json"))
        out.append(d)
    return out


@router.post("/kill-switch/reset/{session_id}")
def reset_kill_switch(session_id: int, request: Request) -> dict[str, Any]:
    runner = _manager(request).runners.get(session_id)
    if runner is None:
        raise HTTPException(404, "session introuvable ou arrêtée")
    runner.reset_kill_switch()
    return {"ok": True}


def _paper_trades(session_id: int) -> list[Trade]:
    rows = (
        get_conn()
        .execute("SELECT * FROM trades WHERE paper_session_id=? ORDER BY entry_ts", (session_id,))
        .fetchall()
    )
    return [
        Trade(
            symbol=r["symbol"],
            direction=Direction(r["direction"]),
            mode=EntryMode(r["mode"]),
            entry_ts=r["entry_ts"],
            exit_ts=r["exit_ts"],
            entry_index=0,
            exit_index=0,
            entry_price=r["entry_price"],
            exit_price=r["exit_price"],
            qty=r["qty"],
            exit_reason=ExitReason(r["exit_reason"]),
            aborted=bool(r["aborted"]),
            pnl_gross=r["pnl_gross"],
            entry_fee=r["entry_fee"],
            exit_fee=r["exit_fee"],
            slippage_cost=r["slippage_cost"],
            funding_cost=r["funding_cost"],
            pnl_net=r["pnl_net"],
            r_multiple=r["r_multiple"],
            mae=r["mae"],
            mfe=r["mfe"],
        )
        for r in rows
    ]


@router.get("/coherence/{session_id}")
def coherence(session_id: int, request: Request) -> dict[str, Any]:
    """Backtest a posteriori sur la période paper + appariement des trades
    (CU6). Utilise les données accumulées par la session (REST + websocket)."""
    runner = _manager(request).runners.get(session_id)
    if runner is None:
        raise HTTPException(404, "session introuvable ou arrêtée (cohérence en session active)")
    row = (
        get_conn()
        .execute("SELECT started_at FROM paper_sessions WHERE id=?", (session_id,))
        .fetchone()
    )
    if row is None:
        raise HTTPException(404, "session inconnue")

    out = run_backtest(runner.md, runner.config, journal="none")
    started = int(row["started_at"])
    bt_trades = [t for t in out.trades if t.entry_ts >= started]
    paper_trades = [t for t in _paper_trades(session_id) if t.entry_ts >= started]
    report = coherence_report(paper_trades, bt_trades, runner.tf_ms)

    conn = get_conn()
    conn.execute(
        "INSERT INTO coherence_reports(session_id, period_start, period_end, pct_identical, "
        "report_json, created_at) VALUES (?,?,?,?,?,?)",
        (
            session_id,
            started,
            runner.guard.last_ts or started,
            report["pct_identiques"],
            json.dumps(report, ensure_ascii=False, default=str),
            started,
        ),
    )
    conn.commit()
    return report
