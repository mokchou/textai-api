"""Datasets : construction (téléchargement + cache Parquet versionné) et
consultation. Le hash est toujours affiché (reproductibilité)."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import PARQUET_DIR
from app.api.jobs import job_manager
from app.data import store
from app.data.datasets import build_dataset
from app.data.exchange import BybitAdapter

router = APIRouter(prefix="/api/datasets", tags=["données"])


class BuildRequest(BaseModel):
    symbol: str
    timeframe: str = "15m"
    start_ts: int
    end_ts: int


@router.get("")
def list_datasets() -> list[dict[str, Any]]:
    out = []
    for row in store.list_datasets():
        row["manifest"] = json.loads(row.pop("manifest_json"))
        out.append(row)
    return out


@router.get("/{dataset_id}")
def get_dataset(dataset_id: int) -> dict[str, Any]:
    row = store.get_dataset(dataset_id)
    if row is None:
        raise HTTPException(404, "dataset introuvable")
    row["manifest"] = json.loads(row.pop("manifest_json"))
    return row


@router.post("/build")
def build(req: BuildRequest) -> dict[str, Any]:
    def run(progress: Any) -> dict[str, Any]:
        adapter = BybitAdapter()
        progress(1, 10)
        ds = build_dataset(
            adapter, req.symbol, req.timeframe, req.start_ts, req.end_ts, PARQUET_DIR
        )
        progress(9, 10)
        dataset_id = store.register_dataset(ds)
        return {"dataset_id": dataset_id, "hash": ds.hash, "manifest": ds.manifest}

    job_id = job_manager.submit("dataset", run)
    return {"job_id": job_id}
