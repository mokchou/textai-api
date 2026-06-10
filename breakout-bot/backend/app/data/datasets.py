"""Datasets versionnés (PRD §4.1) : tout téléchargement est figé en Parquet,
hashé, et référencé par les backtests ⇒ reproductibilité totale.

Un dataset = {symbole, timeframe, période} → 4 Parquet (ohlcv, funding, oi,
basis) + manifest.json. Le hash est calculé sur le contenu CANONIQUE des
tables (colonnes ordonnées, timestamps UTC ms, float64) : re-télécharger une
période close produit le même hash.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from app.data.exchange import TF_MS, ExchangeAdapter

EIGHT_H_MS = 8 * 3600 * 1000


@dataclass(slots=True)
class Dataset:
    symbol: str
    timeframe: str
    start_ts: int
    end_ts: int
    path: Path
    hash: str
    manifest: dict


def _canonical_bytes(df: pd.DataFrame) -> bytes:
    df = df[sorted(df.columns)].sort_values("ts").reset_index(drop=True)
    cols = []
    for c in sorted(df.columns):
        arr = df[c].to_numpy()
        arr = arr.astype(np.int64) if c == "ts" else arr.astype(np.float64)
        cols.append(c.encode() + b"\x00" + arr.tobytes())
    return b"\x01".join(cols)


def dataset_hash(tables: dict[str, pd.DataFrame]) -> str:
    h = hashlib.sha256()
    for name in sorted(tables):
        h.update(name.encode() + b"\x02" + _canonical_bytes(tables[name]))
    return h.hexdigest()


def align_start(start_ms: int, timeframe: str) -> int:
    """Aligne le début sur une frontière de 8 h : garantit que les blocs HTF et
    les échéances de funding coïncident avec les ouvertures de bougies."""
    return ((start_ms + EIGHT_H_MS - 1) // EIGHT_H_MS) * EIGHT_H_MS


def build_dataset(
    adapter: ExchangeAdapter,
    symbol: str,
    timeframe: str,
    start_ms: int,
    end_ms: int,
    root: Path,
) -> Dataset:
    start_ms = align_start(start_ms, timeframe)
    tf_ms = TF_MS[timeframe]
    end_ms = (end_ms // tf_ms) * tf_ms

    ohlcv_rows = adapter.fetch_ohlcv(symbol, timeframe, start_ms, end_ms)
    if not ohlcv_rows:
        raise ValueError(f"Aucune donnée OHLCV pour {symbol} {timeframe} sur la période.")
    ohlcv = pd.DataFrame(ohlcv_rows, columns=["ts", "open", "high", "low", "close", "volume"])
    ohlcv["ts"] = ohlcv["ts"].astype(np.int64)

    funding = pd.DataFrame(
        adapter.fetch_funding_history(symbol, start_ms, end_ms) or [],
        columns=["ts", "rate_pct"],
    )
    lacunes: list[str] = []
    try:
        oi = pd.DataFrame(
            adapter.fetch_open_interest(symbol, timeframe, start_ms, end_ms) or [],
            columns=["ts", "open_interest"],
        )
    except Exception as exc:  # OI souvent limité en profondeur : non bloquant
        oi = pd.DataFrame(columns=["ts", "open_interest"])
        lacunes.append(f"open_interest indisponible : {exc}")
    try:
        basis = pd.DataFrame(
            adapter.fetch_basis(symbol, timeframe, start_ms, end_ms) or [],
            columns=["ts", "basis_pct"],
        )
    except Exception as exc:
        basis = pd.DataFrame(columns=["ts", "basis_pct"])
        lacunes.append(f"basis indisponible : {exc}")

    for df in (funding, oi, basis):
        if len(df):
            df["ts"] = df["ts"].astype(np.int64)

    tables = {"ohlcv": ohlcv, "funding": funding, "oi": oi, "basis": basis}
    h = dataset_hash(tables)

    real_start, real_end = int(ohlcv["ts"].iloc[0]), int(ohlcv["ts"].iloc[-1])
    dirname = f"{symbol}_{timeframe}_{real_start}_{real_end}_{h[:12]}"
    path = root / dirname
    path.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_parquet(path / f"{name}.parquet", index=False)

    manifest = {
        "symbol": symbol,
        "timeframe": timeframe,
        "start_ts": real_start,
        "end_ts": real_end,
        "hash": h,
        "nb_bougies": len(ohlcv),
        "couverture": {
            "funding": len(funding),
            "open_interest": len(oi),
            "basis": len(basis),
        },
        "lacunes": lacunes,
        "construit_le": int(time.time() * 1000),
    }
    (path / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return Dataset(
        symbol=symbol,
        timeframe=timeframe,
        start_ts=real_start,
        end_ts=real_end,
        path=path,
        hash=h,
        manifest=manifest,
    )


def load_dataset(path: Path) -> tuple[dict[str, pd.DataFrame], dict]:
    manifest = json.loads((path / "manifest.json").read_text())
    tables = {
        name: pd.read_parquet(path / f"{name}.parquet")
        for name in ("ohlcv", "funding", "oi", "basis")
    }
    return tables, manifest
