"""Stabilité du grid search : heatmap + détection d'« optimum isolé »
(sur-optimisation probable, PRD §7.6)."""

from __future__ import annotations

from typing import Any

import numpy as np

SEUIL_PLATEAU = 0.7
METRIQUE_DEFAUT = "expectancy_r"


def stability_report(
    results: list[dict[str, Any]], metric: str = METRIQUE_DEFAUT
) -> dict[str, Any]:
    if not results:
        return {"score_plateau": None, "optimum_isole": False, "heatmap": None}

    param_names = sorted(results[0]["params"].keys())
    axes = [sorted({r["params"][p] for r in results}) for p in param_names]
    shape = tuple(len(a) for a in axes)
    grid = np.full(shape, np.nan)
    for r in results:
        idx = tuple(axes[k].index(r["params"][p]) for k, p in enumerate(param_names))
        grid[idx] = r[metric]

    flat_best = int(np.nanargmax(grid))
    best_idx: tuple[int, ...] = tuple(int(k) for k in np.unravel_index(flat_best, shape))
    best_val = float(grid[best_idx])

    # voisins immédiats (toutes dimensions, pas de diagonale)
    neighbors: list[float] = []
    for dim in range(len(shape)):
        for delta in (-1, 1):
            nb = list(best_idx)
            nb[dim] += delta
            if 0 <= nb[dim] < shape[dim]:
                v = grid[tuple(nb)]
                if np.isfinite(v):
                    neighbors.append(float(v))

    if neighbors and best_val > 0:
        score = float(np.mean(neighbors)) / best_val
    elif neighbors:
        score = 1.0 if np.mean(neighbors) >= best_val else 0.0
    else:
        score = 1.0  # un seul point : pas d'évidence d'isolement

    isole = score < SEUIL_PLATEAU
    out: dict[str, Any] = {
        "metrique": metric,
        "parametres": param_names,
        "axes": axes,
        "heatmap": [
            [(float(v) if np.isfinite(v) else None) for v in row] for row in np.atleast_2d(grid)
        ],
        "optimum": {
            "params": {p: axes[k][best_idx[k]] for k, p in enumerate(param_names)},
            "valeur": best_val,
        },
        "score_plateau": score,
        "optimum_isole": isole,
    }
    if isole:
        out["avertissement_fr"] = (
            f"L'optimum est un pic isolé (score de plateau {score:.2f} < "
            f"{SEUIL_PLATEAU}) : risque élevé de sur-optimisation. Préférez une "
            "zone où les voisins restent bons."
        )
    return out
