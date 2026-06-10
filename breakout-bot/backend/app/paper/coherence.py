"""Rapport de cohérence backtest vs paper (PRD §8.6).

Sur une période couverte par les deux, on apparie les trades (direction +
mode + horodatage d'entrée à ± 1 bougie près) et on classe les écarts.
Critère d'acceptation : ≥ 95 % de trades identiques.
"""

from __future__ import annotations

from typing import Any

from app.engine.types import Trade

SEUIL_ACCEPTATION_PCT = 95.0


def coherence_report(
    paper_trades: list[Trade],
    backtest_trades: list[Trade],
    tf_ms: int,
    price_tolerance_pct: float = 0.05,
) -> dict[str, Any]:
    bt_pool = list(backtest_trades)
    matches: list[dict[str, Any]] = []
    unmatched_paper: list[Trade] = []

    for pt in paper_trades:
        found = None
        for bt in bt_pool:
            if (
                bt.direction is pt.direction
                and bt.mode is pt.mode
                and abs(bt.entry_ts - pt.entry_ts) <= tf_ms
            ):
                found = bt
                break
        if found is None:
            unmatched_paper.append(pt)
            continue
        bt_pool.remove(found)
        price_diff_pct = (
            abs(found.entry_price - pt.entry_price) / pt.entry_price * 100.0
            if pt.entry_price
            else 0.0
        )
        matches.append(
            {
                "entry_ts": pt.entry_ts,
                "direction": pt.direction.value,
                "mode": pt.mode.value,
                "identique": price_diff_pct <= price_tolerance_pct
                and found.exit_reason is pt.exit_reason,
                "ecart_prix_entree_pct": price_diff_pct,
                "pnl_paper": pt.pnl_net,
                "pnl_backtest": found.pnl_net,
                "motif_sortie_paper": pt.exit_reason.value,
                "motif_sortie_backtest": found.exit_reason.value,
            }
        )

    n_paper = len(paper_trades)
    identical = sum(1 for m in matches if m["identique"])
    pct = 100.0 * identical / n_paper if n_paper else 100.0

    causes: list[str] = []
    if unmatched_paper:
        causes.append(
            f"{len(unmatched_paper)} trade(s) paper sans équivalent backtest "
            "(divergence de flux de prix websocket vs REST probable)."
        )
    if bt_pool:
        causes.append(f"{len(bt_pool)} trade(s) backtest sans équivalent paper.")
    near = [m for m in matches if not m["identique"]]
    if near:
        causes.append(
            f"{len(near)} trade(s) appariés mais divergents (prix d'entrée ou motif de sortie)."
        )

    return {
        "nb_trades_paper": n_paper,
        "nb_trades_backtest": len(backtest_trades),
        "nb_apparies": len(matches),
        "nb_identiques": identical,
        "pct_identiques": pct,
        "objectif_atteint": pct >= SEUIL_ACCEPTATION_PCT,
        "seuil_pct": SEUIL_ACCEPTATION_PCT,
        "causes_ecarts_fr": causes,
        "appariements": matches,
        "paper_sans_equivalent": [t.to_json() for t in unmatched_paper],
        "backtest_sans_equivalent": [t.to_json() for t in bt_pool],
    }
