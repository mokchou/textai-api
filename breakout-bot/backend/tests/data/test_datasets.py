"""Datasets Parquet versionnés : hash déterministe, manifeste, alignements."""

from __future__ import annotations

import numpy as np
import pytest

from app.data.datasets import align_start, build_dataset, dataset_hash, load_dataset
from app.data.feed import load_market_data, market_data_from_tables
from tests.fixtures.candles import TF_15M_MS, T0, random_walk_market

EIGHT_H = 8 * 3600 * 1000


class FakeAdapter:
    """Adaptateur déterministe : rejoue un marché synthétique comme un exchange."""

    def __init__(self, seed: int = 4, n: int = 2000) -> None:
        self.md = random_walk_market(n=n, seed=seed)

    def fetch_ohlcv(self, symbol, timeframe, start_ms, end_ms):
        m = self.md
        out = []
        for i in range(len(m)):
            if start_ms <= m.ts[i] < end_ms:
                out.append(
                    [int(m.ts[i]), m.open[i], m.high[i], m.low[i], m.close[i], m.volume[i]]
                )
        return out

    def fetch_funding_history(self, symbol, start_ms, end_ms):
        return [
            (int(ts), 0.01)
            for ts in self.md.ts
            if start_ms <= ts < end_ms and ts % EIGHT_H == 0
        ]

    def fetch_open_interest(self, symbol, timeframe, start_ms, end_ms):
        return [
            (int(ts), float(oi))
            for ts, oi in zip(self.md.ts, self.md.oi, strict=True)
            if start_ms <= ts < end_ms
        ]

    def fetch_basis(self, symbol, timeframe, start_ms, end_ms):
        return [
            (int(ts), float(b))
            for ts, b in zip(self.md.ts, self.md.basis_pct, strict=True)
            if start_ms <= ts < end_ms
        ]


def test_align_start_sur_frontiere_8h():
    assert align_start(T0 + 1, "15m") == T0 + EIGHT_H
    assert align_start(T0, "15m") == T0


def test_meme_periode_meme_hash(tmp_path):
    adapter = FakeAdapter()
    end = T0 + 1500 * TF_15M_MS
    ds1 = build_dataset(adapter, "TESTUSDT", "15m", T0, end, tmp_path / "a")
    ds2 = build_dataset(FakeAdapter(), "TESTUSDT", "15m", T0, end, tmp_path / "b")
    assert ds1.hash == ds2.hash  # critère P0 : re-télécharger ⇒ hash identique
    assert ds1.manifest["nb_bougies"] == ds2.manifest["nb_bougies"]

    ds3 = build_dataset(adapter, "TESTUSDT", "15m", T0, end - TF_15M_MS, tmp_path / "c")
    assert ds3.hash != ds1.hash  # période différente ⇒ hash différent


def test_chargement_et_alignement(tmp_path):
    adapter = FakeAdapter()
    end = T0 + 1500 * TF_15M_MS
    ds = build_dataset(adapter, "TESTUSDT", "15m", T0, end, tmp_path)
    tables, manifest = load_dataset(ds.path)
    assert manifest["hash"] == ds.hash
    md = market_data_from_tables(tables, "TESTUSDT", "15m")
    assert len(md) == manifest["nb_bougies"]
    # funding aligné : un taux d'événement aux frontières 8 h, 0 ailleurs
    events = md.ts % EIGHT_H == 0
    assert np.all(md.funding_event_rate_pct[events] == 0.01)
    assert np.all(md.funding_event_rate_pct[~events] == 0.0)
    # OI et basis présents (forward-fill)
    assert np.isfinite(md.oi[10:]).all()
    md2 = load_market_data(ds.path)
    assert np.array_equal(md2.close, md.close)


def test_hash_canonique_independant_de_l_ordre():
    import pandas as pd

    df1 = pd.DataFrame({"ts": [1, 2], "a": [1.0, 2.0], "b": [3.0, 4.0]})
    df2 = pd.DataFrame({"b": [4.0, 3.0], "a": [2.0, 1.0], "ts": [2, 1]})
    assert dataset_hash({"x": df1}) == dataset_hash({"x": df2})


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BREAKOUT_DATA_DIR", str(tmp_path))
    import importlib

    from app.api import deps

    importlib.reload(deps)
    from app.db.connection import init_db

    init_db(deps.DB_PATH)
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


def test_backtest_de_bout_en_bout_via_api(client, tmp_path, relaxed_config):
    """Dataset → backtest (job) → rapport complet → export CSV (CU1)."""
    import time

    from app.data import store
    from app.data.datasets import build_dataset as bd

    ds = bd(FakeAdapter(n=4000), "TESTUSDT", "15m", T0, T0 + 4000 * TF_15M_MS, tmp_path / "ds")
    dataset_id = store.register_dataset(ds)

    r = client.post(
        "/api/backtests",
        json={"dataset_id": dataset_id, "config": relaxed_config.model_dump(mode="json")},
    )
    assert r.status_code == 200, r.text
    job_id, backtest_id = r.json()["job_id"], r.json()["backtest_id"]

    for _ in range(120):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("termine", "erreur"):
            break
        time.sleep(0.25)
    assert job["status"] == "termine", job.get("error")

    bt = client.get(f"/api/backtests/{backtest_id}").json()
    report = bt["report"]
    assert report["run_id"] and report["dataset_hash"] == ds.hash
    assert "attribution_couts" in report and "ventilations" in report
    assert bt["equity"], "courbe d'équité présente"

    csv = client.get(f"/api/backtests/{backtest_id}/trades.csv")
    assert csv.status_code == 200
    assert csv.text.splitlines()[0].startswith("symbole,direction,mode")

    kpi = client.get(f"/api/dashboard/kpis?scope=backtest:{backtest_id}").json()
    assert "metriques" in kpi and "attribution_couts" in kpi
