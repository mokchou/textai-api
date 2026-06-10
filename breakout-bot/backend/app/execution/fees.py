"""Frais maker/taker (PRD §6.1).

Mode 1 = taker à l'entrée ; Mode 2 = maker à l'entrée ; toutes les sorties
(stop, trailing, invalidation, time, kill, avorté) = taker en v1.
"""

from __future__ import annotations

from app.config.models import CostConfig
from app.engine.types import EntryMode


def entry_fee(price: float, qty: float, mode: EntryMode, cfg: CostConfig) -> float:
    pct = cfg.taker_fee_pct if mode is EntryMode.MODE_1 else cfg.maker_fee_pct
    return price * qty * pct / 100.0


def exit_fee(price: float, qty: float, cfg: CostConfig) -> float:
    return price * qty * cfg.taker_fee_pct / 100.0
