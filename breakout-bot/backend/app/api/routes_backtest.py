"""Backtests : lancement (job), résultats, export CSV des trades, comparaison."""

from __future__ import annotations

import csv
import io
import json
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import load_active_config
from app.api.jobs import job_manager
from app.backtest.results import build_report, equity_series
from app.backtest.runner import run_backtest
from app.config.models import BotConfig
from app.data import store
from app.data.feed import load_market_data
from app.db.connection import get_conn
from app.engine.version import ENGINE_VERSION

router = APIRouter(prefix="/api/backtests", tags=["backtest"])


class BacktestRequest(BaseModel):
    dataset_id: int
    config: dict[str, Any] | None = None  # défaut : configuration active


@router.post("")
def launch(req: BacktestRequest) -> dict[str, Any]:
    ds_row = store.get_dataset(req.dataset_id)
    if ds_row is None:
        raise HTTPException(404, "dataset introuvable")
    cfg = BotConfig.model_validate(req.config) if req.config else load_active_config()

    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO backtests(run_id, dataset_id, engine_version, status, started_at) "
        "VALUES ('', ?, ?, 'en_cours', ?)",
        (req.dataset_id, ENGINE_VERSION, int(time.time() * 1000)),
    )
    conn.commit()
    backtest_id = int(cur.lastrowid)

    def run(progress: Any) -> dict[str, Any]:
        md = load_market_data(store.dataset_path(req.dataset_id))
        out = run_backtest(md, cfg, journal="interesting", progress_cb=progress)
        report = build_report(out, md, cfg, ds_row["hash"])
        equity = equity_series(out, md)
        c = get_conn()
        c.execute(
            "UPDATE backtests SET run_id=?, status='termine', finished_at=?, report_json=?, "
            "equity_json=? WHERE id=?",
            (
                report["run_id"],
                int(time.time() * 1000),
                json.dumps(report, ensure_ascii=False, default=str),
                json.dumps(equity),
                backtest_id,
            ),
        )
        for t in out.trades:
            c.execute(
                "INSERT INTO trades(backtest_id, symbol, direction, mode, entry_ts, exit_ts, "
                "entry_price, exit_price, qty, exit_reason, aborted, pnl_gross, entry_fee, "
                "exit_fee, slippage_cost, funding_cost, pnl_net, r_multiple, mae, mfe, signals_json) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    backtest_id,
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
        c.commit()
        return {"backtest_id": backtest_id, "run_id": report["run_id"]}

    job_id = job_manager.submit("backtest", run)
    return {"job_id": job_id, "backtest_id": backtest_id}


@router.get("")
def list_backtests() -> list[dict[str, Any]]:
    rows = (
        get_conn()
        .execute(
            "SELECT b.id, b.run_id, b.status, b.started_at, b.finished_at, b.engine_version, "
            "d.symbol, d.timeframe, d.hash AS dataset_hash "
            "FROM backtests b LEFT JOIN datasets d ON d.id = b.dataset_id ORDER BY b.id DESC"
        )
        .fetchall()
    )
    return [dict(r) for r in rows]


@router.get("/compare")
def compare(
    ids: str = Query(..., description="ids séparés par des virgules (2 à 4)"),
) -> list[dict]:
    id_list = [int(x) for x in ids.split(",") if x.strip()]
    if not 2 <= len(id_list) <= 4:
        raise HTTPException(422, "comparaison de 2 à 4 backtests")
    return [get_backtest(i) for i in id_list]


@router.get("/{backtest_id}")
def get_backtest(backtest_id: int) -> dict[str, Any]:
    row = get_conn().execute("SELECT * FROM backtests WHERE id=?", (backtest_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "backtest introuvable")
    d = dict(row)
    d["report"] = json.loads(d.pop("report_json")) if d.get("report_json") else None
    d["equity"] = json.loads(d.pop("equity_json")) if d.get("equity_json") else None
    return d


@router.get("/{backtest_id}/trades.csv")
def trades_csv(backtest_id: int) -> StreamingResponse:
    rows = (
        get_conn()
        .execute("SELECT * FROM trades WHERE backtest_id=? ORDER BY entry_ts", (backtest_id,))
        .fetchall()
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "symbole",
            "direction",
            "mode",
            "entree_ts",
            "sortie_ts",
            "prix_entree",
            "prix_sortie",
            "quantite",
            "motif_sortie",
            "avorte",
            "pnl_brut",
            "frais_entree",
            "frais_sortie",
            "slippage",
            "funding",
            "pnl_net",
            "r_multiple",
            "mae",
            "mfe",
            "signaux",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                r["symbol"],
                r["direction"],
                r["mode"],
                r["entry_ts"],
                r["exit_ts"],
                r["entry_price"],
                r["exit_price"],
                r["qty"],
                r["exit_reason"],
                r["aborted"],
                r["pnl_gross"],
                r["entry_fee"],
                r["exit_fee"],
                r["slippage_cost"],
                r["funding_cost"],
                r["pnl_net"],
                r["r_multiple"],
                r["mae"],
                r["mfe"],
                r["signals_json"],
            ]
        )
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=trades_backtest_{backtest_id}.csv"},
    )
