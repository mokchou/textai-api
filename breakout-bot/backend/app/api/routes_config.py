"""Configuration : schéma FR complet (labels + info-bulles), validation en
temps réel, presets, import/export JSON."""

from __future__ import annotations

import json
import time
from typing import Any, Literal, get_args, get_origin

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ValidationError

from app.api.deps import load_active_config, save_active_config
from app.config.hashing import config_hash
from app.config.models import GROUPS_FR, BotConfig
from app.db.connection import get_conn

router = APIRouter(prefix="/api/config", tags=["configuration"])
router_presets = APIRouter(prefix="/api/configs", tags=["configuration"])


def _field_schema(name: str, field: Any) -> dict[str, Any]:
    extra = field.json_schema_extra or {}
    ann = field.annotation
    ftype = "number"
    options: list[str] | None = None
    if ann is bool:
        ftype = "boolean"
    elif ann is int:
        ftype = "integer"
    elif get_origin(ann) is Literal:
        ftype = "choice"
        options = [str(v) for v in get_args(ann)]
    elif ann is not float and ann is not int:
        ftype = "json"
    minimum = maximum = None
    for m in field.metadata:
        minimum = getattr(m, "ge", minimum)
        maximum = getattr(m, "le", maximum)
    default = field.get_default(call_default_factory=True)
    if isinstance(default, list):
        default = [d.model_dump() if isinstance(d, BaseModel) else d for d in default]
    return {
        "name": name,
        "type": ftype,
        "label_fr": extra.get("label_fr", name),
        "tooltip_fr": extra.get("tooltip_fr"),
        "unit": extra.get("unit"),
        "default": default,
        "min": minimum,
        "max": maximum,
        "options": options,
    }


@router.get("/schema")
def config_schema() -> dict[str, Any]:
    groups = []
    for group_name, group_field in BotConfig.model_fields.items():
        model = group_field.annotation
        fields = [_field_schema(n, f) for n, f in model.model_fields.items()]  # type: ignore[union-attr]
        groups.append(
            {
                "key": group_name,
                "label_fr": GROUPS_FR.get(group_name, group_name),
                "fields": fields,
            }
        )
    return {"groups": groups}


@router.get("/defaults")
def config_defaults() -> dict[str, Any]:
    return BotConfig().model_dump(mode="json")


@router.get("/active")
def get_active() -> dict[str, Any]:
    cfg = load_active_config()
    return {"config": cfg.model_dump(mode="json"), "config_hash": config_hash(cfg)}


@router.put("/active")
def put_active(payload: dict[str, Any]) -> dict[str, Any]:
    cfg = _validate(payload)
    save_active_config(cfg)
    return {"ok": True, "config_hash": config_hash(cfg)}


@router.post("/validate")
def validate_config(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        cfg = _validate(payload)
    except HTTPException as exc:
        return {"valide": False, "erreurs_fr": exc.detail}
    return {"valide": True, "erreurs_fr": [], "config_hash": config_hash(cfg)}


def _validate(payload: dict[str, Any]) -> BotConfig:
    try:
        return BotConfig.model_validate(payload)
    except ValidationError as exc:
        msgs = []
        for err in exc.errors():
            loc = ".".join(str(x) for x in err["loc"])
            msg = err["msg"]
            if msg.startswith("Value error, "):
                msg = msg[len("Value error, ") :]
            msgs.append(f"{loc} : {msg}" if loc else msg)
        raise HTTPException(status_code=422, detail=msgs) from exc


# ----------------------------- presets ------------------------------------ #


@router_presets.get("")
def list_presets() -> list[dict[str, Any]]:
    rows = (
        get_conn()
        .execute("SELECT id, name, config_hash, created_at FROM configs ORDER BY id DESC")
        .fetchall()
    )
    return [dict(r) for r in rows]


@router_presets.post("")
def save_preset(payload: dict[str, Any]) -> dict[str, Any]:
    name = payload.get("name") or "sans nom"
    cfg = _validate(payload.get("config", {}))
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO configs(name, json, config_hash, created_at) VALUES (?,?,?,?)",
        (name, cfg.model_dump_json(), config_hash(cfg), int(time.time() * 1000)),
    )
    conn.commit()
    return {"id": cur.lastrowid, "config_hash": config_hash(cfg)}


@router_presets.get("/{preset_id}")
def get_preset(preset_id: int) -> dict[str, Any]:
    row = get_conn().execute("SELECT * FROM configs WHERE id=?", (preset_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "préréglage introuvable")
    d = dict(row)
    d["config"] = json.loads(d.pop("json"))
    return d
