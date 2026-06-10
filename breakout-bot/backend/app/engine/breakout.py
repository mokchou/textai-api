"""Qualité de la bougie de cassure (PRD §5.3) : volume, corps, mèche de rejet.

Évaluée à la clôture de la bougie de cassure, pour le Mode 1 (confirmation
a posteriori du fill intra-bougie) comme pour le Mode 2 (précondition).
"""

from __future__ import annotations

import math
from typing import Any

from app.config.models import EntryConfig
from app.engine.types import Candle, Direction


def breakout_candle_quality(
    candle: Candle, volume_rank: float, direction: Direction, cfg: EntryConfig
) -> tuple[bool, dict[str, Any]]:
    """Vérifie volume ≥ percentile, corps ≥ %, mèche opposée ≤ %."""
    rng = candle.range_
    signals: dict[str, Any] = {"volume_rank": volume_rank}
    reasons: list[str] = []

    if math.isnan(volume_rank) or volume_rank < cfg.volume_percentile:
        reasons.append(
            f"volume insuffisant (P{volume_rank:.0f} < P{cfg.volume_percentile})"
            if not math.isnan(volume_rank)
            else "volume : fenêtre de chauffe"
        )

    if rng <= 0:
        reasons.append("bougie sans amplitude")
        signals["raisons"] = reasons
        return False, signals

    body_pct = 100.0 * candle.body / rng
    signals["corps_pct"] = body_pct
    if body_pct < cfg.body_min_pct:
        reasons.append(f"corps {body_pct:.0f} % < {cfg.body_min_pct:.0f} %")

    # mèche opposée au sens du trade : basse pour un long, haute pour un short
    if direction is Direction.LONG:
        wick = min(candle.open, candle.close) - candle.low
    else:
        wick = candle.high - max(candle.open, candle.close)
    wick_pct = 100.0 * wick / rng
    signals["meche_opposee_pct"] = wick_pct
    if wick_pct > cfg.wick_max_pct:
        reasons.append(f"mèche de rejet {wick_pct:.0f} % > {cfg.wick_max_pct:.0f} %")

    signals["raisons"] = reasons
    return not reasons, signals
