"""Tests unitaires des composants du moteur : range, qualité de cassure,
sessions, filtres crypto, régime."""

from __future__ import annotations

import numpy as np
import pytest

from app.config.models import BotConfig
from app.engine.breakout import breakout_candle_quality
from app.engine.crypto_filters import evaluate_crypto_filters
from app.engine.feed import MarketView, precompute
from app.engine.sessions import in_exclusion_window
from app.engine.types import Candle, Direction
from tests.fixtures.candles import make_market

# --------------------------------------------------------------------------- #
# Détection de range
# --------------------------------------------------------------------------- #


def _range_market(n_osc: int = 60):
    """Oscillation propre entre 98 et 102 : un range évident."""
    candles = []
    for k in range(n_osc):
        if k % 2 == 0:
            candles.append((99.0, 102.0, 98.0, 101.0, 10.0))
        else:
            candles.append((101.0, 102.0, 98.0, 99.0, 10.0))
    return make_market(candles)


def test_range_detecte_sur_oscillation(relaxed_config):
    md = _range_market()
    ind = precompute(md, relaxed_config)
    assert ind.ranges.valid.any(), "un range évident doit être détecté"
    j = int(np.where(ind.ranges.valid)[0][0])
    assert ind.ranges.low[j] == pytest.approx(98.0)
    assert ind.ranges.high[j] == pytest.approx(102.0)
    assert ind.ranges.touches_low[j] >= relaxed_config.range_detection.min_touches


def test_range_rejete_si_pas_assez_de_touches(relaxed_config):
    # tendance : aucun rebond répété sur des bornes
    candles = [(100 + k, 101 + k, 99.5 + k, 100.8 + k, 10.0) for k in range(60)]
    md = make_market(candles)
    cfg = relaxed_config.model_copy(deep=True)
    cfg.range_detection.min_touches = 3
    ind = precompute(md, cfg)
    assert not ind.ranges.valid.any()


# --------------------------------------------------------------------------- #
# Qualité de la bougie de cassure
# --------------------------------------------------------------------------- #


def _candle(o, h, lo, c):
    return Candle(ts=0, open=o, high=h, low=lo, close=c, volume=100.0)


def test_cassure_confirmee_corps_plein():
    cfg = BotConfig().entries
    ok, sig = breakout_candle_quality(_candle(100, 103, 99.9, 102.9), 90.0, Direction.LONG, cfg)
    assert ok, sig


def test_cassure_rejetee_volume_faible():
    cfg = BotConfig().entries
    ok, sig = breakout_candle_quality(_candle(100, 103, 99.9, 102.9), 50.0, Direction.LONG, cfg)
    assert not ok
    assert any("volume" in r for r in sig["raisons"])


def test_cassure_rejetee_meche_de_rejet():
    cfg = BotConfig().entries
    # long avec grande mèche basse (rejet) : open 100, low 97, close 102.9, high 103
    ok, sig = breakout_candle_quality(_candle(100, 103, 97.0, 102.9), 90.0, Direction.LONG, cfg)
    assert not ok
    assert any("mèche" in r for r in sig["raisons"])


def test_cassure_rejetee_petit_corps():
    cfg = BotConfig().entries
    ok, sig = breakout_candle_quality(_candle(100, 103, 99.0, 100.5), 90.0, Direction.LONG, cfg)
    assert not ok
    assert any("corps" in r for r in sig["raisons"])


# --------------------------------------------------------------------------- #
# Sessions
# --------------------------------------------------------------------------- #


def test_fenetres_exclusion_funding_et_opens():
    cfg = BotConfig().sessions
    h = 3600 * 1000

    def ts(hh, mm):
        return hh * h + mm * 60 * 1000  # jour epoch 0 (UTC)

    assert in_exclusion_window(ts(0, 15), cfg)[0]  # ±30 min autour de 00 h
    assert in_exclusion_window(ts(23, 45), cfg)[0]  # la fenêtre de minuit déborde la veille
    assert in_exclusion_window(ts(8, 0), cfg)[0]
    assert in_exclusion_window(ts(16, 29), cfg)[0]
    assert in_exclusion_window(ts(13, 45), cfg)[0]  # open US 13 h 30
    assert not in_exclusion_window(ts(5, 0), cfg)[0]
    assert not in_exclusion_window(ts(10, 0), cfg)[0]

    cfg2 = cfg.model_copy(deep=True)
    cfg2.funding_exclusion_enabled = False
    cfg2.open_exclusions = []
    assert not in_exclusion_window(ts(8, 0), cfg2)[0]


# --------------------------------------------------------------------------- #
# Filtres crypto
# --------------------------------------------------------------------------- #


def _view(funding=0.01, oi=(100.0, 101.0), basis=0.05):
    candles = [(100.0, 100.5, 99.5, 100.2, 10.0)] * 2
    md = make_market(candles, funding_rate_pct=funding, oi=list(oi), basis_pct=basis)
    cfg = BotConfig()
    view = MarketView(md, precompute(md, cfg))
    view.set_index(1)
    return view


def test_funding_trop_positif_bloque_le_long():
    cfg = BotConfig().crypto_filters
    res = evaluate_crypto_filters(_view(funding=0.08), Direction.LONG, cfg)
    assert not res.entry_allowed
    res2 = evaluate_crypto_filters(_view(funding=0.08), Direction.SHORT, cfg)
    assert res2.entry_allowed


def test_oi_en_baisse_interdit_mode1_seulement():
    cfg = BotConfig().crypto_filters
    res = evaluate_crypto_filters(_view(oi=(100.0, 99.0)), Direction.LONG, cfg)
    assert res.entry_allowed and not res.mode1_allowed
    res2 = evaluate_crypto_filters(_view(oi=(100.0, 102.0)), Direction.LONG, cfg)
    assert res2.entry_allowed and res2.mode1_allowed


def test_basis_excessif_bloque_l_entree():
    cfg = BotConfig().crypto_filters
    res = evaluate_crypto_filters(_view(basis=0.8), Direction.LONG, cfg)
    assert not res.entry_allowed


def test_donnees_manquantes_neutralisent_le_filtre():
    cfg = BotConfig().crypto_filters
    view = _view()
    view.md.oi = np.full(2, np.nan)
    view.md.basis_pct = np.full(2, np.nan)
    view.md.funding_rate_pct = np.full(2, np.nan)
    res = evaluate_crypto_filters(view, Direction.LONG, cfg)
    assert res.entry_allowed and res.mode1_allowed
    assert "oi_filtre" in res.signals  # le rapport doit mentionner la neutralisation
