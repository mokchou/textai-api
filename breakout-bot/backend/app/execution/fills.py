"""Règles de fill « anti-fantaisie » (PRD table 6.4) — fonctions pures.

Chaque fonction retourne le PRIX ÉQUITABLE du fill (avant slippage) ou None si
l'ordre n'est pas exécuté sur la bougie. Le slippage et les frais sont
appliqués par le simulateur.
"""

from __future__ import annotations

from app.engine.types import Direction


def stop_entry_fill(
    direction: Direction, trigger: float, open_: float, high: float, low: float
) -> tuple[float, bool] | None:
    """Ordre stop d'entrée (Mode 1) : fill au prix de déclenchement (+ slippage
    par le simulateur). Gap d'ouverture au-delà du déclencheur ⇒ fill à l'open
    réel (jamais mieux que le marché)."""
    if direction is Direction.LONG:
        if open_ >= trigger:
            return open_, True
        if high >= trigger:
            return trigger, False
    else:
        if open_ <= trigger:
            return open_, True
        if low <= trigger:
            return trigger, False
    return None


def limit_entry_fill(
    direction: Direction,
    limit: float,
    low: float,
    high: float,
    min_penetration: float,
) -> float | None:
    """Ordre limit (Mode 2) : fill SEULEMENT si le prix pénètre le niveau d'au
    moins `min_penetration` (en prix). Un simple touch exact ne compte pas.
    Fill au prix limit — jamais mieux (modèle conservateur)."""
    if direction is Direction.LONG:
        if low <= limit - min_penetration:
            return limit
    else:
        if high >= limit + min_penetration:
            return limit
    return None


def protection_stop_fill(
    direction: Direction, stop: float, open_: float, high: float, low: float
) -> tuple[float, bool] | None:
    """Stop de protection : fill au prix du stop (− slippage par le simulateur),
    jamais mieux. Gap d'ouverture au-delà du stop ⇒ fill à l'open réel."""
    if direction is Direction.LONG:
        if open_ <= stop:
            return open_, True
        if low <= stop:
            return stop, False
    else:
        if open_ >= stop:
            return open_, True
        if high >= stop:
            return stop, False
    return None
