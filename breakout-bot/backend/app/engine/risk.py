"""Dimensionnement et stops (PRD §5.8) — fonctions pures, utilisées au fill.

Taille = (équité × risque_par_trade_%) / distance au stop. Jamais de taille fixe.
"""

from __future__ import annotations

from app.config.models import RiskConfig
from app.engine.types import Direction


def stop_distance(atr_value: float, direction: Direction, cfg: RiskConfig) -> float:
    mult = cfg.stop_atr_mult_long if direction is Direction.LONG else cfg.stop_atr_mult_short
    return mult * atr_value


def position_qty(
    equity: float, entry_price: float, stop_dist: float, direction: Direction, cfg: RiskConfig
) -> float:
    if stop_dist <= 0 or entry_price <= 0:
        return 0.0
    qty = (equity * cfg.risk_per_trade_pct / 100.0) / stop_dist
    if direction is Direction.SHORT:
        qty *= cfg.short_size_mult
    return qty


def stop_price(entry_price: float, stop_dist: float, direction: Direction) -> float:
    return entry_price - direction.sign * stop_dist


def trailing_stop(
    extreme_price: float, atr_value: float, direction: Direction, cfg: RiskConfig
) -> float:
    return extreme_price - direction.sign * cfg.trailing_atr_mult * atr_value
