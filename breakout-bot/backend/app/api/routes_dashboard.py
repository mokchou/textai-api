"""Tableau de bord : KPIs unifiés backtest / paper (exigence utilisateur n°1)."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException

from app.db.connection import get_conn
from app.engine.types import Direction, EntryMode, ExitReason, Trade
from app.metrics.compute import compute_metrics
from app.metrics.cost_attribution import cost_attribution

router = APIRouter(prefix="/api/dashboard", tags=["tableau de bord"])


def _trades_from_rows(rows: list) -> list[Trade]:
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


@router.get("/kpis")
def kpis(scope: str) -> dict[str, Any]:
    """`scope` = `backtest:{id}` ou `paper:{session_id}`."""
    kind, _, ident = scope.partition(":")
    if kind == "backtest":
        row = (
            get_conn()
            .execute("SELECT report_json FROM backtests WHERE id=?", (int(ident),))
            .fetchone()
        )
        if row is None or not row["report_json"]:
            raise HTTPException(404, "backtest introuvable ou non terminé")
        report = json.loads(row["report_json"])
        return {
            "scope": scope,
            "metriques": report["metriques"],
            "attribution_couts": report["attribution_couts"],
            "ventilations": report["ventilations"],
        }
    if kind == "paper":
        rows = (
            get_conn()
            .execute(
                "SELECT * FROM trades WHERE paper_session_id=? ORDER BY exit_ts", (int(ident),)
            )
            .fetchall()
        )
        srow = (
            get_conn()
            .execute("SELECT config_json FROM paper_sessions WHERE id=?", (int(ident),))
            .fetchone()
        )
        if srow is None:
            raise HTTPException(404, "session paper introuvable")
        initial = json.loads(srow["config_json"])["market"]["initial_equity"]
        trades = _trades_from_rows(rows)
        # équité réalisée reconstruite aux clôtures de trades
        equity = (
            np.array([initial + s for s in np.cumsum([t.pnl_net for t in trades])])
            if trades
            else np.array([initial])
        )
        ts = (
            np.array([t.exit_ts for t in trades], dtype=np.int64)
            if trades
            else np.array([0], dtype=np.int64)
        )
        fallback = any(t.funding_cost != 0 for t in trades)  # approximation
        return {
            "scope": scope,
            "metriques": compute_metrics(trades, equity, ts, initial),
            "attribution_couts": cost_attribution(trades, fallback_funding_used=fallback),
            "equite": [
                {"ts": int(t.exit_ts), "equite": float(initial + c)}
                for t, c in zip(trades, np.cumsum([t.pnl_net for t in trades]), strict=True)
            ],
        }
    raise HTTPException(422, "scope attendu : backtest:{id} ou paper:{session_id}")
