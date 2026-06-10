"""Filtres de session (PRD §5.7) : fenêtres d'exclusion des ENTRÉES uniquement.

Les sorties de protection ne sont jamais suspendues.
"""

from __future__ import annotations

from app.config.models import SessionConfig

DAY_MS = 24 * 3600 * 1000
FUNDING_HOURS_UTC = (0, 8, 16)


def in_exclusion_window(ts_ms: int, cfg: SessionConfig) -> tuple[bool, str | None]:
    """`ts_ms` est dans une fenêtre d'exclusion ? Retourne (exclu, libellé)."""
    minute_of_day = (ts_ms % DAY_MS) // 60000

    def near(center_min: int, half_width: int) -> bool:
        d = abs(minute_of_day - center_min)
        return min(d, 1440 - d) <= half_width

    if cfg.funding_exclusion_enabled:
        for h in FUNDING_HOURS_UTC:
            if near(h * 60, cfg.funding_exclusion_half_width_min):
                return True, f"funding {h:02d}h UTC"
    for win in cfg.open_exclusions:
        if near(win.hour_utc * 60 + win.minute_utc, win.half_width_min):
            return True, win.label or f"open {win.hour_utc:02d}h{win.minute_utc:02d}"
    return False, None
