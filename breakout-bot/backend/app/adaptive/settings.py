"""Réglages du module de ré-optimisation adaptative.

Distincts de la config de stratégie (qui, elle, entre dans le config_hash des
backtests) : ils pilotent QUAND et COMMENT les paramètres sont ré-optimisés.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class AdaptiveSettings(BaseModel):
    enabled: bool = False
    mode: Literal["approbation_manuelle", "auto"] = "approbation_manuelle"
    # déclenchement hebdomadaire : dimanche 00:00 UTC par défaut
    cron_day_of_week: str = "sun"
    cron_hour_utc: int = 0
    # fenêtre d'optimisation : N derniers jours (train + test du walk-forward)
    lookback_days: int = 240
    train_days: int = 180
    test_days: int = 60
    # paramètres adaptables (chemins pointés), 3 max balayés à la fois
    adaptive_params: list[str] = Field(
        default_factory=lambda: [
            "range_detection.compression_percentile",
            "entries.volume_percentile",
            "regime.adx_min",
        ]
    )
    grid_points: int = 3  # points testés par paramètre, centrés sur la valeur active
    # garde-fous
    min_plateau_score: float = 0.7
    min_profit_factor_test: float = 1.1
    max_drawdown_test_pct: float = 15.0
    max_param_delta_pct: float = 30.0
    metric: str = "expectancy_r"


def load_settings(path: Path) -> AdaptiveSettings:
    if path.exists():
        return AdaptiveSettings.model_validate(json.loads(path.read_text()))
    return AdaptiveSettings()


def save_settings(settings: AdaptiveSettings, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(settings.model_dump_json(indent=2))
