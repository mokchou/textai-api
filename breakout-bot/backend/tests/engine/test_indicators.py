"""Indicateurs : valeurs de référence et CAUSALITÉ (aucune fuite du futur)."""

from __future__ import annotations

import numpy as np
import pytest

from app.engine import indicators as ind


@pytest.fixture
def random_series():
    rng = np.random.default_rng(42)
    n = 600
    close = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    high = close * (1 + np.abs(rng.normal(0, 0.005, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.005, n)))
    volume = rng.lognormal(0, 0.5, n) * 100
    return high, low, close, volume


def test_atr_constant_sur_bougies_identiques():
    n = 100
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    close = np.full(n, 100.0)
    a = ind.atr(high, low, close, 14)
    assert np.isnan(a[:13]).all()
    assert a[13:] == pytest.approx(np.full(n - 13, 2.0))


def test_percentile_rank_simple():
    v = np.array([1.0, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    r = ind.rolling_percentile_rank(v, 5)
    assert np.isnan(r[:4]).all()
    assert r[4:] == pytest.approx(np.full(6, 100.0))  # toujours le max de sa fenêtre
    r2 = ind.rolling_percentile_rank(v[::-1].copy(), 5)
    assert r2[4:] == pytest.approx(np.full(6, 0.0))  # toujours le min


def test_hurst_tendance_vs_retour_moyenne():
    n = 800
    rng = np.random.default_rng(1)
    trending = 100 * np.exp(np.cumsum(np.full(n, 0.002) + rng.normal(0, 0.001, n)))
    h_trend = ind.hurst_rs(trending, 100, 1)
    # série anti-persistante : alternance forcée
    mean_rev = 100 + np.where(np.arange(n) % 2 == 0, 1.0, -1.0) + rng.normal(0, 0.05, n)
    h_rev = ind.hurst_rs(mean_rev, 100, 1)
    assert np.nanmean(h_trend[200:]) > 0.55
    assert np.nanmean(h_rev[200:]) < 0.45


@pytest.mark.parametrize(
    "name",
    ["atr", "adx", "bollinger_width", "volume_rank", "hurst"],
)
def test_causalite_par_troncature(random_series, name):
    """La valeur à l'index i ne change pas si on tronque les données après i."""
    high, low, close, volume = random_series
    t = 400  # point de troncature

    def compute(h, lo, c, v):
        if name == "atr":
            return ind.atr(h, lo, c, 14)
        if name == "adx":
            return ind.adx(h, lo, c, 14)
        if name == "bollinger_width":
            return ind.bollinger_width(c, 20)
        if name == "volume_rank":
            return ind.rolling_percentile_rank(v, 50)
        return ind.hurst_rs(c, 100, 5)

    full = compute(high, low, close, volume)
    trunc = compute(high[:t], low[:t], close[:t], volume[:t])
    np.testing.assert_allclose(full[:t], trunc, equal_nan=True, rtol=1e-12)
