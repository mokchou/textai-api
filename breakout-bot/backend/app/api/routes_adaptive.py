"""Ré-optimisation adaptative : réglages, cycle (manuel ou planifié),
propositions avec garde-fous, application gouvernée, historique d'audit."""

from __future__ import annotations

import json
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.adaptive import journal as adaptive_journal
from app.adaptive.guardrails import check_proposal
from app.adaptive.optimizer import run_adaptive_optimization
from app.adaptive.settings import AdaptiveSettings, load_settings, save_settings
from app.api.deps import (
    ADAPTIVE_SETTINGS_PATH,
    PARQUET_DIR,
    load_active_config,
    save_active_config,
)
from app.api.jobs import job_manager
from app.api.ws import hub
from app.config.models import BotConfig
from app.data.datasets import build_dataset
from app.data.exchange import BybitAdapter
from app.data.feed import market_data_from_tables
from app.optimize.grid import set_param

router = APIRouter(prefix="/api/adaptive", tags=["adaptation"])


@router.get("/settings")
def get_settings() -> dict[str, Any]:
    return load_settings(ADAPTIVE_SETTINGS_PATH).model_dump(mode="json")


@router.put("/settings")
def put_settings(payload: dict[str, Any]) -> dict[str, Any]:
    settings = AdaptiveSettings.model_validate(payload)
    save_settings(settings, ADAPTIVE_SETTINGS_PATH)
    return {"ok": True}


@router.get("/history")
def history(limit: int = 100) -> list[dict[str, Any]]:
    out = []
    for row in adaptive_journal.list_changes(limit):
        for key in ("old_config_json", "new_config_json", "diff_json", "guardrail_report_json"):
            if row.get(key):
                row[key.replace("_json", "")] = json.loads(row.pop(key))
        out.append(row)
    return out


def run_adaptive_cycle(
    paper_manager: Any, trigger_kind: str, progress: Any = None
) -> dict[str, Any]:
    """Cycle complet : données récentes → walk-forward → garde-fous →
    proposition journalisée → application (mode auto uniquement)."""
    settings = load_settings(ADAPTIVE_SETTINGS_PATH)
    active = load_active_config()
    symbol = active.market.symbols[0]
    now = int(time.time() * 1000)
    start = now - settings.lookback_days * 86_400_000

    adapter = BybitAdapter()
    ds = build_dataset(adapter, symbol, active.market.timeframe, start, now, PARQUET_DIR)
    from app.data.datasets import load_dataset

    tables, manifest = load_dataset(ds.path)
    md = market_data_from_tables(tables, symbol, active.market.timeframe)

    result = run_adaptive_optimization(md, active, settings, progress_cb=progress)
    proposed = result["params_proposes"]
    current = result["params_actuels"]

    position_open = paper_manager.any_position_open() if paper_manager else False
    guard = check_proposal(settings, result["walkforward"], current, proposed, position_open)

    new_cfg = active.model_copy(deep=True)
    for path, value in (proposed or {}).items():
        set_param(new_cfg, path, value)
    new_cfg = BotConfig.model_validate(new_cfg.model_dump())
    diff = adaptive_journal.make_diff(
        active.model_dump(mode="json"), new_cfg.model_dump(mode="json")
    )

    if not guard.passed:
        status = "rejetee"
    elif not diff:
        status = "rejetee"
        guard.reasons_fr.append("Les paramètres proposés sont identiques aux paramètres actifs.")
    elif settings.mode == "auto":
        status = "auto_appliquee"
    else:
        status = "proposee"

    change_id = adaptive_journal.record_proposal(
        trigger_kind=trigger_kind,
        old_config=active.model_dump(mode="json"),
        new_config=new_cfg.model_dump(mode="json"),
        diff=diff,
        wf_job_id=None,
        stability_score=result["walkforward"].get("stabilite_derniere_fenetre"),
        guardrail_report=guard.to_json(),
        status=status,
    )

    if status == "auto_appliquee":
        save_active_config(new_cfg)
        if paper_manager is not None:
            paper_manager.apply_config(new_cfg)

    summary = {
        "change_id": change_id,
        "status": status,
        "diff": diff,
        "garde_fous": guard.to_json(),
        "stabilite": result["walkforward"].get("stabilite_derniere_fenetre"),
        "metriques_test": result["walkforward"].get("metriques_agregees_test"),
        "dataset_hash": manifest["hash"],
    }
    hub.broadcast("adaptive:events", summary)
    return summary


@router.post("/run-now")
def run_now(request: Request) -> dict[str, Any]:
    paper_manager = getattr(request.app.state, "paper_manager", None)
    job_id = job_manager.submit(
        "adaptive", lambda progress: run_adaptive_cycle(paper_manager, "manuel", progress)
    )
    return {"job_id": job_id}


@router.post("/proposals/{change_id}/approve")
def approve(change_id: int, request: Request) -> dict[str, Any]:
    change = adaptive_journal.get_change(change_id)
    if change is None:
        raise HTTPException(404, "proposition introuvable")
    if change["status"] != "proposee":
        raise HTTPException(409, f"proposition au statut « {change['status']} », non applicable")
    new_cfg = BotConfig.model_validate(json.loads(change["new_config_json"]))
    save_active_config(new_cfg)
    paper_manager = getattr(request.app.state, "paper_manager", None)
    if paper_manager is not None:
        paper_manager.apply_config(new_cfg)
    adaptive_journal.set_status(change_id, "appliquee")
    hub.broadcast("adaptive:events", {"change_id": change_id, "status": "appliquee"})
    return {"ok": True}


@router.post("/proposals/{change_id}/reject")
def reject(change_id: int) -> dict[str, Any]:
    change = adaptive_journal.get_change(change_id)
    if change is None:
        raise HTTPException(404, "proposition introuvable")
    adaptive_journal.set_status(change_id, "rejetee")
    return {"ok": True}
