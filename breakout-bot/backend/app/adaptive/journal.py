"""Journal d'audit des changements de paramètres (table param_changes)."""

from __future__ import annotations

import json
import time
from typing import Any

from app.db.connection import get_conn


def record_proposal(
    trigger_kind: str,
    old_config: dict,
    new_config: dict,
    diff: dict,
    wf_job_id: int | None,
    stability_score: float | None,
    guardrail_report: dict,
    status: str,
) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO param_changes(ts, trigger_kind, old_config_json, new_config_json, "
        "diff_json, wf_job_id, stability_score, guardrail_report_json, status) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (
            int(time.time() * 1000),
            trigger_kind,
            json.dumps(old_config, ensure_ascii=False),
            json.dumps(new_config, ensure_ascii=False),
            json.dumps(diff, ensure_ascii=False),
            wf_job_id,
            stability_score,
            json.dumps(guardrail_report, ensure_ascii=False),
            status,
        ),
    )
    conn.commit()
    assert cur.lastrowid is not None
    return int(cur.lastrowid)


def set_status(change_id: int, status: str) -> None:
    conn = get_conn()
    applied_at = int(time.time() * 1000) if status in ("appliquee", "auto_appliquee") else None
    conn.execute(
        "UPDATE param_changes SET status=?, applied_at=COALESCE(?, applied_at) WHERE id=?",
        (status, applied_at, change_id),
    )
    conn.commit()


def get_change(change_id: int) -> dict[str, Any] | None:
    row = get_conn().execute("SELECT * FROM param_changes WHERE id=?", (change_id,)).fetchone()
    return dict(row) if row else None


def list_changes(limit: int = 100) -> list[dict[str, Any]]:
    rows = (
        get_conn()
        .execute("SELECT * FROM param_changes ORDER BY ts DESC LIMIT ?", (limit,))
        .fetchall()
    )
    return [dict(r) for r in rows]


def make_diff(old: dict, new: dict, prefix: str = "") -> dict[str, Any]:
    """Diff plat {chemin: {avant, apres}} entre deux configs sérialisées."""
    diff: dict[str, Any] = {}
    for key in old.keys() | new.keys():
        path = f"{prefix}.{key}" if prefix else key
        ov, nv = old.get(key), new.get(key)
        if isinstance(ov, dict) and isinstance(nv, dict):
            diff.update(make_diff(ov, nv, path))
        elif ov != nv:
            diff[path] = {"avant": ov, "apres": nv}
    return diff
