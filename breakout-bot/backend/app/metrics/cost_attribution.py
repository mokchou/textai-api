"""Rapport d'attribution des coûts (exigence clé PRD §11).

« Sur 100 € de PnL brut, X € de frais, Y € de slippage, Z € de funding
→ N € nets. » Si les coûts dépassent 40 % du PnL brut, avertissement
explicite : l'edge est fragile.
"""

from __future__ import annotations

from typing import Any

from app.engine.types import Trade

SEUIL_EDGE_FRAGILE_PCT = 40.0


def cost_attribution(trades: list[Trade], fallback_funding_used: bool) -> dict[str, Any]:
    brut = sum(t.pnl_gross for t in trades)
    frais = sum(t.entry_fee + t.exit_fee for t in trades)
    slippage = sum(t.slippage_cost for t in trades)
    funding = sum(t.funding_cost for t in trades)
    net = brut - frais - slippage - funding
    couts = frais + slippage + funding

    out: dict[str, Any] = {
        "pnl_brut": brut,
        "frais": frais,
        "slippage": slippage,
        "funding": funding,
        "pnl_net": net,
        "couts_totaux": couts,
        "funding_taux_de_repli_utilise": fallback_funding_used,
    }

    if brut > 0:
        ratio = couts / brut * 100.0
        out["ratio_couts_pct"] = ratio
        out["edge_fragile"] = ratio > SEUIL_EDGE_FRAGILE_PCT
        out["pour_100_brut"] = {
            "frais": frais / brut * 100.0,
            "slippage": slippage / brut * 100.0,
            "funding": funding / brut * 100.0,
            "net": net / brut * 100.0,
        }
        if out["edge_fragile"]:
            out["avertissement_fr"] = (
                f"Les coûts représentent {ratio:.0f} % du PnL brut (seuil "
                f"{SEUIL_EDGE_FRAGILE_PCT:.0f} %) : l'edge est fragile — toute "
                "dégradation des conditions d'exécution peut le faire disparaître."
            )
    else:
        out["ratio_couts_pct"] = None
        out["edge_fragile"] = brut < 0
        if brut < 0:
            out["avertissement_fr"] = "PnL brut négatif : la stratégie perd avant même les coûts."
    if fallback_funding_used:
        out["note_funding_fr"] = (
            "Des échéances de funding sans taux historique ont utilisé le taux de repli."
        )
    return out
