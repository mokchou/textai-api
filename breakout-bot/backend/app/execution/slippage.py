"""Modèles de slippage (PRD §6.2) — retournent un écart de prix (≥ 0).

Appliqués aux exécutions au marché/stop uniquement ; les fills limit (Mode 2)
n'ont pas de slippage (leur coût implicite est le modèle de fill conservateur).
"""

from __future__ import annotations

import math

from app.config.models import CostConfig


def slippage_amount(price: float, atr_value: float, cfg: CostConfig) -> float:
    if cfg.slippage_model == "volatilite":
        if math.isnan(atr_value):
            return price * cfg.slippage_bps / 10_000.0  # repli pendant la chauffe
        return cfg.slippage_atr_coef * atr_value
    base = price * cfg.slippage_bps / 10_000.0
    if cfg.slippage_model == "stress":
        return base * cfg.stress_multiplier
    return base
