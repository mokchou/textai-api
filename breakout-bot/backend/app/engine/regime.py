"""Filtre de régime (PRD §5.6) : ADX et exposant de Hurst.

Régime défavorable ⇒ aucun range n'est armé.
"""

from __future__ import annotations

import math
from typing import Any

from app.config.models import RegimeConfig
from app.engine.feed import MarketView


def regime_ok(view: MarketView, cfg: RegimeConfig) -> tuple[bool, dict[str, Any]]:
    adx = view.indicator("adx")
    hurst = view.indicator("hurst")
    signals: dict[str, Any] = {"adx": adx, "hurst": hurst}

    if math.isnan(adx) or math.isnan(hurst):
        signals["raison"] = "indicateurs de régime en période de chauffe"
        return False, signals

    if adx < cfg.adx_min:
        signals["raison"] = f"ADX {adx:.1f} < seuil {cfg.adx_min:.0f}"
        return False, signals

    if cfg.adx_rising_required and view.i >= cfg.adx_slope_lookback:
        past = view.indicator("adx", -cfg.adx_slope_lookback)
        signals["adx_pente"] = adx - past
        if math.isnan(past) or adx <= past:
            signals["raison"] = "ADX non croissant"
            return False, signals

    if hurst <= cfg.hurst_min:
        signals["raison"] = f"Hurst {hurst:.2f} ≤ seuil {cfg.hurst_min:.2f}"
        return False, signals

    return True, signals
