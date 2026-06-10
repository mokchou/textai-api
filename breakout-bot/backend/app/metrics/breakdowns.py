"""Ventilations (PRD §11) : long/short, Mode 1/Mode 2, avortés — chaque
sous-ensemble avec ses propres métriques."""

from __future__ import annotations

from typing import Any

import numpy as np

from app.engine.types import Direction, EntryMode, Trade
from app.metrics.compute import compute_metrics


def compute_breakdowns(
    trades: list[Trade],
    equity_curve: np.ndarray,
    ts: np.ndarray,
    initial_equity: float,
) -> dict[str, Any]:
    subsets: dict[str, list[Trade]] = {
        "long": [t for t in trades if t.direction is Direction.LONG],
        "short": [t for t in trades if t.direction is Direction.SHORT],
        "mode_1": [t for t in trades if t.mode is EntryMode.MODE_1],
        "mode_2": [t for t in trades if t.mode is EntryMode.MODE_2],
        "avortes": [t for t in trades if t.aborted],
    }
    return {
        name: compute_metrics(sub, equity_curve, ts, initial_equity)
        for name, sub in subsets.items()
    }
