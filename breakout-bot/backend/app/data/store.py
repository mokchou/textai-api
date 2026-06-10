"""Registre des datasets en SQLite + collecte continue d'open interest."""

from __future__ import annotations

import json
import time
from pathlib import Path

from app.data.datasets import Dataset
from app.db.connection import get_conn


def register_dataset(ds: Dataset) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO datasets(symbol, timeframe, start_ts, end_ts, hash, path, manifest_json, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            ds.symbol,
            ds.timeframe,
            ds.start_ts,
            ds.end_ts,
            ds.hash,
            str(ds.path),
            json.dumps(ds.manifest, ensure_ascii=False),
            int(time.time() * 1000),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_datasets() -> list[dict]:
    rows = get_conn().execute("SELECT * FROM datasets ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def get_dataset(dataset_id: int) -> dict | None:
    row = get_conn().execute("SELECT * FROM datasets WHERE id=?", (dataset_id,)).fetchone()
    return dict(row) if row else None


def dataset_path(dataset_id: int) -> Path:
    row = get_dataset(dataset_id)
    if row is None:
        raise KeyError(f"dataset {dataset_id} introuvable")
    return Path(row["path"])


def record_oi_snapshot(symbol: str, ts: int, open_interest: float) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO oi_collector(symbol, ts, open_interest) VALUES (?,?,?)",
        (symbol, ts, open_interest),
    )
    conn.commit()
