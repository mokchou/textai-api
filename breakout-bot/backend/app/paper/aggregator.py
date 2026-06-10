"""Validation de continuité du flux de bougies live (PRD §8.1).

Le moteur ne décide JAMAIS sur un historique troué : toute bougie manquante
est re-fetchée par REST avant traitement.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LiveCandle:
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float


FetchMissing = Callable[[int, int], list[LiveCandle]]  # (start_ms, end_ms) → bougies closes


class ContinuityGuard:
    """Garantit une suite de bougies contiguës ; comble les trous via REST."""

    def __init__(self, tf_ms: int, fetch_missing: FetchMissing) -> None:
        self.tf_ms = tf_ms
        self.fetch_missing = fetch_missing
        self.last_ts: int | None = None

    def ingest(self, candle: LiveCandle) -> list[LiveCandle]:
        """Retourne les bougies à traiter, dans l'ordre, trous comblés."""
        if candle.ts % self.tf_ms != 0:
            raise ValueError(f"bougie non alignée sur le timeframe : ts={candle.ts}")
        if self.last_ts is None:
            self.last_ts = candle.ts
            return [candle]
        expected = self.last_ts + self.tf_ms
        if candle.ts == self.last_ts:
            return []  # doublon (re-push de la même bougie close)
        if candle.ts < self.last_ts:
            return []  # bougie en retard, déjà traitée
        out: list[LiveCandle] = []
        if candle.ts > expected:
            missing = self.fetch_missing(expected, candle.ts)
            got = {c.ts for c in missing}
            want = set(range(expected, candle.ts, self.tf_ms))
            if want - got:
                raise RuntimeError(
                    f"bougies manquantes non récupérables : {sorted(want - got)[:5]}…"
                )
            out.extend(sorted((c for c in missing if c.ts in want), key=lambda c: c.ts))
        out.append(candle)
        self.last_ts = candle.ts
        return out
