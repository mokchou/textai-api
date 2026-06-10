"""Garde-fous et mécanique de proposition du module adaptatif."""

from __future__ import annotations

from app.adaptive.guardrails import check_proposal
from app.adaptive.journal import make_diff
from app.adaptive.optimizer import candidate_values
from app.adaptive.settings import AdaptiveSettings
from app.config.models import BotConfig


def wf_report(plateau=0.9, pf=1.5, dd=5.0):
    return {
        "stabilite_derniere_fenetre": plateau,
        "metriques_agregees_test": {"profit_factor": pf, "max_drawdown_pct": dd},
    }


def test_proposition_acceptee():
    rep = check_proposal(
        AdaptiveSettings(),
        wf_report(),
        current_params={"regime.adx_min": 22.0},
        proposed_params={"regime.adx_min": 24.0},
        position_open=False,
    )
    assert rep.passed and not rep.reasons_fr


def test_rejet_optimum_isole():
    rep = check_proposal(
        AdaptiveSettings(),
        wf_report(plateau=0.4),
        {"regime.adx_min": 22.0},
        {"regime.adx_min": 24.0},
        position_open=False,
    )
    assert not rep.passed
    assert any("sur-optimisation" in r for r in rep.reasons_fr)


def test_rejet_profit_factor_et_drawdown():
    rep = check_proposal(
        AdaptiveSettings(),
        wf_report(pf=0.9, dd=30.0),
        {"regime.adx_min": 22.0},
        {"regime.adx_min": 24.0},
        position_open=False,
    )
    assert not rep.passed
    assert not rep.checks["profit_factor"]
    assert not rep.checks["drawdown"]


def test_rejet_delta_trop_brutal():
    rep = check_proposal(
        AdaptiveSettings(max_param_delta_pct=30.0),
        wf_report(),
        {"regime.adx_min": 20.0},
        {"regime.adx_min": 30.0},  # +50 %
        position_open=False,
    )
    assert not rep.passed
    assert any("brutal" in r for r in rep.reasons_fr)


def test_report_si_position_ouverte():
    rep = check_proposal(
        AdaptiveSettings(),
        wf_report(),
        {"regime.adx_min": 22.0},
        {"regime.adx_min": 24.0},
        position_open=True,
    )
    assert not rep.passed
    assert any("reportée" in r for r in rep.reasons_fr)


def test_valeurs_candidates_bornees_par_le_schema():
    cfg = BotConfig()
    vals = candidate_values(cfg, "regime.adx_min", 3)
    assert all(15 <= v <= 35 for v in vals)  # bornes du PRD §9.4
    assert cfg.regime.adx_min in vals  # centrées sur la valeur active
    vals_int = candidate_values(cfg, "range_detection.compression_percentile", 3)
    assert all(isinstance(v, int) for v in vals_int)


def test_diff_de_configs():
    a = BotConfig().model_dump(mode="json")
    cfg2 = BotConfig()
    cfg2.regime.adx_min = 28.0
    b = cfg2.model_dump(mode="json")
    diff = make_diff(a, b)
    assert diff == {"regime.adx_min": {"avant": 22.0, "apres": 28.0}}
