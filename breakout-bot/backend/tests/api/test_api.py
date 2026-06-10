"""API FastAPI : schéma de config FR, validation, presets, jobs."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config.models import BotConfig


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BREAKOUT_DATA_DIR", str(tmp_path))
    import importlib

    from app.api import deps

    importlib.reload(deps)
    from app.db.connection import init_db

    init_db(deps.DB_PATH)
    # app sans lifespan (pas de websocket Bybit ni de scheduler en test)
    from app.main import create_app

    app = create_app()
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def test_schema_complet_avec_infobulles(client):
    r = client.get("/api/config/schema")
    assert r.status_code == 200
    groups = r.json()["groups"]
    keys = {g["key"] for g in groups}
    assert {
        "range_detection",
        "entries",
        "crypto_filters",
        "regime",
        "risk",
        "sessions",
        "costs",
        "market",
    } <= keys
    nb_fields = sum(len(g["fields"]) for g in groups)
    assert nb_fields >= 35  # les ~35 paramètres du PRD §9
    for g in groups:
        assert g["label_fr"]
        for f in g["fields"]:
            assert f["label_fr"], f
            # chaque paramètre numérique porte ses bornes
            if f["type"] in ("number", "integer") and f["name"] != "initial_equity":
                assert f["min"] is not None and f["max"] is not None, f


def test_validation_regles_croisees_en_francais(client):
    cfg = BotConfig().model_dump(mode="json")
    cfg["risk"]["trailing_atr_mult"] = 3.0
    cfg["risk"]["stop_atr_mult_long"] = 2.0
    r = client.post("/api/config/validate", json=cfg)
    body = r.json()
    assert not body["valide"]
    assert any("trailing" in e for e in body["erreurs_fr"])


def test_validation_bornes(client):
    cfg = BotConfig().model_dump(mode="json")
    cfg["risk"]["risk_per_trade_pct"] = 50.0  # hors bornes 0.1–2
    r = client.post("/api/config/validate", json=cfg)
    assert not r.json()["valide"]


def test_config_active_aller_retour(client):
    r = client.get("/api/config/active")
    cfg = r.json()["config"]
    cfg["regime"]["adx_min"] = 25.0
    r2 = client.put("/api/config/active", json=cfg)
    assert r2.status_code == 200
    r3 = client.get("/api/config/active")
    assert r3.json()["config"]["regime"]["adx_min"] == 25.0
    assert r3.json()["config_hash"] != ""


def test_presets_import_export(client):
    cfg = BotConfig().model_dump(mode="json")
    r = client.post("/api/configs", json={"name": "test", "config": cfg})
    pid = r.json()["id"]
    r2 = client.get(f"/api/configs/{pid}")
    assert r2.json()["config"]["risk"]["risk_per_trade_pct"] == 0.75
    assert client.get("/api/configs").json()[0]["name"] == "test"


def test_reglages_adaptatifs(client):
    r = client.get("/api/adaptive/settings")
    s = r.json()
    assert s["mode"] == "approbation_manuelle"  # mode manuel par défaut
    s["enabled"] = True
    s["mode"] = "auto"
    assert client.put("/api/adaptive/settings", json=s).status_code == 200
    assert client.get("/api/adaptive/settings").json()["mode"] == "auto"


def test_job_inconnu(client):
    assert client.get("/api/jobs/deadbeef").json()["status"] == "inconnu"
