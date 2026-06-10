from __future__ import annotations

import pytest

from app.config.models import BotConfig


@pytest.fixture
def default_config() -> BotConfig:
    return BotConfig()


def make_relaxed_config() -> BotConfig:
    """Config assouplie pour générer de l'activité sur les marchés synthétiques
    (tests d'intégration, anti-look-ahead, reproductibilité, performance)."""
    cfg = BotConfig()
    cfg.market.range_tf_multiple = 1
    cfg.range_detection.min_touches = 2
    cfg.range_detection.window = 30
    cfg.range_detection.touch_tolerance_pct = 0.3
    cfg.range_detection.compression_percentile = 50
    cfg.range_detection.height_min_atr = 0.5
    cfg.range_detection.height_max_atr = 10.0
    cfg.regime.adx_min = 15
    cfg.regime.adx_rising_required = False
    cfg.regime.hurst_min = 0.45
    cfg.regime.hurst_window = 50
    cfg.entries.volume_percentile = 50
    cfg.entries.volume_window = 30
    cfg.entries.body_min_pct = 40.0
    cfg.entries.wick_max_pct = 60.0
    cfg.crypto_filters.oi_filter_enabled = False
    cfg.crypto_filters.basis_filter_enabled = False
    cfg.risk.short_mode2_only = False
    return BotConfig.model_validate(cfg.model_dump())


@pytest.fixture
def relaxed_config() -> BotConfig:
    return make_relaxed_config()
