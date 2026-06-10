"""Garde-fous de la ré-optimisation automatique : une proposition de
paramètres n'est applicable que si elle passe TOUTES les vérifications.
Chaque rejet est journalisé avec sa raison en français."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.adaptive.settings import AdaptiveSettings


@dataclass(slots=True)
class GuardrailReport:
    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    reasons_fr: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {"passed": self.passed, "checks": self.checks, "reasons_fr": self.reasons_fr}


def check_proposal(
    settings: AdaptiveSettings,
    wf_report: dict[str, Any],
    current_params: dict[str, float],
    proposed_params: dict[str, float],
    position_open: bool,
) -> GuardrailReport:
    rep = GuardrailReport(passed=True)

    def fail(check: str, reason: str) -> None:
        rep.passed = False
        rep.checks[check] = False
        rep.reasons_fr.append(reason)

    def ok(check: str) -> None:
        rep.checks[check] = True

    plateau = wf_report.get("stabilite_derniere_fenetre")
    if plateau is None or plateau < settings.min_plateau_score:
        fail(
            "plateau",
            f"Score de plateau {plateau if plateau is not None else 'inconnu'} < "
            f"{settings.min_plateau_score} : optimum isolé, sur-optimisation probable.",
        )
    else:
        ok("plateau")

    agg = wf_report.get("metriques_agregees_test", {})
    pf = agg.get("profit_factor", 0.0)
    if pf < settings.min_profit_factor_test:
        fail(
            "profit_factor",
            f"Profit factor test {pf:.2f} < minimum requis {settings.min_profit_factor_test:.2f}.",
        )
    else:
        ok("profit_factor")

    dd = agg.get("max_drawdown_pct", 100.0)
    if dd > settings.max_drawdown_test_pct:
        fail(
            "drawdown",
            f"Drawdown test {dd:.1f} % > enveloppe autorisée "
            f"{settings.max_drawdown_test_pct:.1f} %.",
        )
    else:
        ok("drawdown")

    for path, new_val in proposed_params.items():
        cur = current_params.get(path)
        if cur is None or cur == 0:
            continue
        delta_pct = abs(new_val - cur) / abs(cur) * 100.0
        if delta_pct > settings.max_param_delta_pct:
            fail(
                "delta_max",
                f"« {path} » bougerait de {delta_pct:.0f} % (max "
                f"{settings.max_param_delta_pct:.0f} %) : changement trop brutal.",
            )
    rep.checks.setdefault("delta_max", True)

    if position_open:
        fail(
            "position_ouverte",
            "Une position est ouverte : application reportée au prochain créneau.",
        )
    else:
        ok("position_ouverte")

    return rep
