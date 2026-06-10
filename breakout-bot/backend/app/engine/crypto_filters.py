"""Confirmations crypto pré-entrée (PRD §5.5) : open interest, funding, basis.

Chaque filtre est individuellement activable ; données manquantes (NaN) ⇒ le
filtre se neutralise pour la bougie et le signale (exigence PRD §4.1).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from app.config.models import CryptoFiltersConfig
from app.engine.feed import MarketView
from app.engine.types import Direction


@dataclass(slots=True)
class CryptoFilterResult:
    entry_allowed: bool  # funding + basis OK (sinon aucune entrée)
    mode1_allowed: bool  # OI : Δ ≥ seuil requis pour le Mode 1
    signals: dict[str, Any] = field(default_factory=dict)
    reasons_fr: list[str] = field(default_factory=list)


def evaluate_crypto_filters(
    view: MarketView, direction: Direction, cfg: CryptoFiltersConfig
) -> CryptoFilterResult:
    signals: dict[str, Any] = {}
    reasons: list[str] = []
    entry_allowed = True
    mode1_allowed = True

    # --- Funding -------------------------------------------------------------
    funding = view.funding_now()
    signals["funding_pct_8h"] = funding
    if math.isnan(funding):
        signals["funding_filtre"] = "données absentes — filtre neutralisé"
    elif direction is Direction.LONG and funding > cfg.funding_max_long:
        entry_allowed = False
        reasons.append(f"funding {funding:+.3f} %/8 h > max achat {cfg.funding_max_long:+.3f} %")
    elif direction is Direction.SHORT and funding < cfg.funding_min_short:
        entry_allowed = False
        reasons.append(f"funding {funding:+.3f} %/8 h < min vente {cfg.funding_min_short:+.3f} %")

    # --- Basis spot/perp -------------------------------------------------------
    if cfg.basis_filter_enabled:
        basis = view.basis_now()
        signals["basis_pct"] = basis
        if math.isnan(basis):
            signals["basis_filtre"] = "données absentes — filtre neutralisé"
        elif abs(basis) > cfg.basis_max_pct:
            entry_allowed = False
            reasons.append(f"basis {basis:+.2f} % > écart max {cfg.basis_max_pct:.2f} %")

    # --- Open interest ---------------------------------------------------------
    if cfg.oi_filter_enabled:
        delta = view.oi_delta_pct()
        signals["oi_delta_pct"] = delta
        if math.isnan(delta):
            signals["oi_filtre"] = "données absentes — filtre neutralisé"
        elif delta < cfg.oi_min_delta_pct:
            mode1_allowed = False
            reasons.append(
                f"OI {delta:+.2f} % < seuil {cfg.oi_min_delta_pct:+.2f} % : "
                "mouvement non soutenu, Mode 1 interdit (Mode 2 seul autorisé)"
            )

    return CryptoFilterResult(
        entry_allowed=entry_allowed,
        mode1_allowed=mode1_allowed,
        signals=signals,
        reasons_fr=reasons,
    )
