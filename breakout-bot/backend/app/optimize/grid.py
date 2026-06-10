"""Grid search (PRD §7.6) : balayage de 1 à 3 paramètres, parallélisé par
processus. Chaque combinaison = un backtest complet sur le même dataset."""

from __future__ import annotations

import itertools
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Any

from app.backtest.runner import run_backtest
from app.config.models import BotConfig
from app.engine.feed import MarketData
from app.metrics.compute import compute_metrics

# état par worker : le dataset est chargé une fois par processus
_worker_md: MarketData | None = None


@dataclass(frozen=True, slots=True)
class GridParam:
    """Paramètre balayé : chemin pointé ('regime.adx_min') + valeurs."""

    path: str
    values: tuple[float, ...]


def set_param(cfg: BotConfig, path: str, value: Any) -> None:
    section, name = path.split(".", 1)
    setattr(getattr(cfg, section), name, value)


def _init_worker(md: MarketData) -> None:
    global _worker_md
    _worker_md = md


def _run_combo(args: tuple[dict[str, Any], dict[str, Any]]) -> dict[str, Any]:
    base_cfg, combo = args
    assert _worker_md is not None
    cfg = BotConfig.model_validate(base_cfg)
    for path, value in combo.items():
        set_param(cfg, path, value)
    cfg = BotConfig.model_validate(cfg.model_dump())  # re-valide les règles croisées
    out = run_backtest(_worker_md, cfg, journal="none")
    m = compute_metrics(out.trades, out.equity_curve, _worker_md.ts, cfg.market.initial_equity)
    return {
        "params": combo,
        "pnl_net": m["pnl_net"],
        "expectancy_r": m["expectancy_r"],
        "profit_factor": m["profit_factor"],
        "nb_trades": m["nb_trades"],
        "max_drawdown_pct": m["max_drawdown_pct"],
        "sharpe": m["sharpe"],
    }


def run_grid(
    md: MarketData,
    base_config: BotConfig,
    params: list[GridParam],
    max_workers: int = 4,
    progress_cb: Any = None,
) -> list[dict[str, Any]]:
    if not 1 <= len(params) <= 3:
        raise ValueError("Le grid search balaie 1 à 3 paramètres.")
    combos = [
        dict(zip([p.path for p in params], values, strict=True))
        for values in itertools.product(*[p.values for p in params])
    ]
    base = base_config.model_dump()
    results: list[dict[str, Any]] = []
    with ProcessPoolExecutor(
        max_workers=max_workers, initializer=_init_worker, initargs=(md,)
    ) as pool:
        for k, res in enumerate(pool.map(_run_combo, [(base, c) for c in combos])):
            results.append(res)
            if progress_cb is not None:
                progress_cb(k + 1, len(combos))
    return results
