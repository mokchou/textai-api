"""Chemins et ressources partagées de l'application."""

from __future__ import annotations

import json
import os
from pathlib import Path

from app.config.models import BotConfig

DATA_DIR = Path(os.environ.get("BREAKOUT_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))
PARQUET_DIR = DATA_DIR / "parquet"
DB_PATH = DATA_DIR / "breakout.sqlite"
ACTIVE_CONFIG_PATH = DATA_DIR / "active_config.json"
ADAPTIVE_SETTINGS_PATH = DATA_DIR / "adaptive_settings.json"


def load_active_config() -> BotConfig:
    if ACTIVE_CONFIG_PATH.exists():
        return BotConfig.model_validate(json.loads(ACTIVE_CONFIG_PATH.read_text()))
    return BotConfig()


def save_active_config(cfg: BotConfig) -> None:
    ACTIVE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE_CONFIG_PATH.write_text(cfg.model_dump_json(indent=2))
