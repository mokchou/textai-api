"""Optimiseur adaptatif : walk-forward sur la fenêtre récente, autour des
valeurs actives des paramètres adaptables."""

from __future__ import annotations

from typing import Any

from app.adaptive.settings import AdaptiveSettings
from app.config.models import BotConfig
from app.engine.feed import MarketData
from app.optimize.grid import GridParam
from app.optimize.walkforward import run_walkforward


def get_param(cfg: BotConfig, path: str) -> float:
    section, name = path.split(".", 1)
    return float(getattr(getattr(cfg, section), name))


def _bounds(cfg_cls: type[BotConfig], path: str) -> tuple[float | None, float | None]:
    section, name = path.split(".", 1)
    f = cfg_cls.model_fields[section].annotation.model_fields[name]  # type: ignore[union-attr]
    ge = le = None
    for m in f.metadata:
        ge = getattr(m, "ge", ge)
        le = getattr(m, "le", le)
    return ge, le


def candidate_values(cfg: BotConfig, path: str, points: int) -> tuple[float, ...]:
    """Valeurs candidates centrées sur la valeur active, bornées par le schéma."""
    current = get_param(cfg, path)
    ge, le = _bounds(type(cfg), path)
    spread = 0.2 * abs(current) if current else 1.0
    raw = [current + spread * k for k in range(-(points // 2), points // 2 + 1)]
    vals = []
    is_int = isinstance(getattr(getattr(cfg, path.split(".")[0]), path.split(".")[1]), int)
    for v in raw:
        if ge is not None:
            v = max(v, float(ge))
        if le is not None:
            v = min(v, float(le))
        vals.append(round(v) if is_int else round(v, 4))
    return tuple(dict.fromkeys(vals))  # déduplique en conservant l'ordre


def run_adaptive_optimization(
    md: MarketData,
    active_config: BotConfig,
    settings: AdaptiveSettings,
    max_workers: int = 4,
    progress_cb: Any = None,
) -> dict[str, Any]:
    params = [
        GridParam(path=p, values=candidate_values(active_config, p, settings.grid_points))
        for p in settings.adaptive_params[:3]
    ]
    wf = run_walkforward(
        md,
        active_config,
        params,
        train_days=settings.train_days,
        test_days=settings.test_days,
        max_workers=max_workers,
        metric=settings.metric,
        progress_cb=progress_cb,
    )
    current = {p.path: get_param(active_config, p.path) for p in params}
    return {
        "walkforward": wf,
        "params_actuels": current,
        "params_proposes": wf["derniers_params"],
    }
