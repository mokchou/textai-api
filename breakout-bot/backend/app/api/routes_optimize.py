"""Grid search & walk-forward (jobs), avec rapport de stabilité."""

from __future__ import annotations

import json
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import load_active_config
from app.api.jobs import job_manager
from app.config.models import BotConfig
from app.data import store
from app.data.feed import load_market_data
from app.db.connection import get_conn
from app.optimize.grid import GridParam, run_grid
from app.optimize.stability import stability_report
from app.optimize.walkforward import run_walkforward

router = APIRouter(prefix="/api/optimize", tags=["optimisation"])


class ParamSpec(BaseModel):
    path: str
    values: list[float]


class GridRequest(BaseModel):
    dataset_id: int
    params: list[ParamSpec] = Field(min_length=1, max_length=3)
    config: dict[str, Any] | None = None
    metric: str = "expectancy_r"
    max_workers: int = 4


class WalkForwardRequest(GridRequest):
    train_days: int = 180
    test_days: int = 60


def _prepare(req: GridRequest) -> tuple[Any, BotConfig, list[GridParam], int]:
    if store.get_dataset(req.dataset_id) is None:
        raise HTTPException(404, "dataset introuvable")
    cfg = BotConfig.model_validate(req.config) if req.config else load_active_config()
    params = [GridParam(path=p.path, values=tuple(p.values)) for p in req.params]
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO optimize_jobs(kind, dataset_id, base_config_json, params_json, status, created_at) "
        "VALUES (?,?,?,?, 'en_cours', ?)",
        (
            "grid" if not isinstance(req, WalkForwardRequest) else "walkforward",
            req.dataset_id,
            cfg.model_dump_json(),
            json.dumps([p.model_dump() for p in req.params]),
            int(time.time() * 1000),
        ),
    )
    conn.commit()
    return store.dataset_path(req.dataset_id), cfg, params, int(cur.lastrowid)


def _finish(opt_id: int, results: Any, stability: Any) -> None:
    get_conn().execute(
        "UPDATE optimize_jobs SET status='termine', finished_at=?, results_json=?, stability_json=? "
        "WHERE id=?",
        (
            int(time.time() * 1000),
            json.dumps(results, ensure_ascii=False, default=str),
            json.dumps(stability, ensure_ascii=False, default=str) if stability else None,
            opt_id,
        ),
    )
    get_conn().commit()


@router.post("/grid")
def launch_grid(req: GridRequest) -> dict[str, Any]:
    path, cfg, params, opt_id = _prepare(req)

    def run(progress: Any) -> dict[str, Any]:
        md = load_market_data(path)
        results = run_grid(md, cfg, params, max_workers=req.max_workers, progress_cb=progress)
        stab = stability_report(results, metric=req.metric)
        _finish(opt_id, results, stab)
        return {"optimize_id": opt_id, "results": results, "stabilite": stab}

    return {"job_id": job_manager.submit("grid", run), "optimize_id": opt_id}


@router.post("/walkforward")
def launch_walkforward(req: WalkForwardRequest) -> dict[str, Any]:
    path, cfg, params, opt_id = _prepare(req)

    def run(progress: Any) -> dict[str, Any]:
        md = load_market_data(path)
        report = run_walkforward(
            md,
            cfg,
            params,
            train_days=req.train_days,
            test_days=req.test_days,
            max_workers=req.max_workers,
            metric=req.metric,
            progress_cb=progress,
        )
        _finish(opt_id, report, None)
        return {"optimize_id": opt_id, "walkforward": report}

    return {"job_id": job_manager.submit("walkforward", run), "optimize_id": opt_id}


@router.get("/jobs")
def list_jobs() -> list[dict[str, Any]]:
    rows = (
        get_conn()
        .execute(
            "SELECT id, kind, dataset_id, status, created_at, finished_at FROM optimize_jobs "
            "ORDER BY id DESC LIMIT 50"
        )
        .fetchall()
    )
    return [dict(r) for r in rows]


@router.get("/jobs/{opt_id}")
def get_job(opt_id: int) -> dict[str, Any]:
    row = get_conn().execute("SELECT * FROM optimize_jobs WHERE id=?", (opt_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "job d'optimisation introuvable")
    d = dict(row)
    for key in ("results_json", "stability_json", "params_json", "base_config_json"):
        if d.get(key):
            d[key.replace("_json", "")] = json.loads(d.pop(key))
        else:
            d.pop(key, None)
    return d
