"""Indicateurs techniques causaux, en numpy pur.

Règle absolue : la valeur à l'index i n'utilise que des données d'index ≤ i.
Les périodes de chauffe sont remplies de NaN. La causalité est vérifiée par
test (troncature du tableau après i ⇒ valeur à i inchangée).
"""

from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view


def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    tr = np.empty_like(high)
    if len(high) == 0:
        return tr
    tr[0] = high[0] - low[0]
    prev_close = close[:-1]
    tr[1:] = np.maximum.reduce(
        [high[1:] - low[1:], np.abs(high[1:] - prev_close), np.abs(low[1:] - prev_close)]
    )
    return tr


def _wilder_smooth(values: np.ndarray, period: int) -> np.ndarray:
    """Lissage de Wilder : seed = moyenne simple des `period` premières valeurs."""
    n = len(values)
    out = np.full(n, np.nan)
    if n < period:
        return out
    out[period - 1] = values[:period].mean()
    alpha = 1.0 / period
    for i in range(period, n):
        out[i] = out[i - 1] + alpha * (values[i] - out[i - 1])
    return out


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    return _wilder_smooth(true_range(high, low, close), period)


def adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(high)
    out = np.full(n, np.nan)
    if n < 2 * period:
        return out
    up = high[1:] - high[:-1]
    down = low[:-1] - low[1:]
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = true_range(high, low, close)[1:]

    atr_s = _wilder_smooth(tr, period)
    plus_s = _wilder_smooth(plus_dm, period)
    minus_s = _wilder_smooth(minus_dm, period)
    with np.errstate(divide="ignore", invalid="ignore"):
        plus_di = 100.0 * plus_s / atr_s
        minus_di = 100.0 * minus_s / atr_s
        dx = 100.0 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
    dx = np.where(np.isfinite(dx), dx, np.nan)

    # ADX = lissage de Wilder du DX (en ignorant la chauffe NaN)
    adx_arr = np.full(n - 1, np.nan)
    start = period - 1  # premier DX valide
    valid = dx[start:]
    if len(valid) >= period:
        sm = _wilder_smooth(valid, period)
        adx_arr[start:] = sm
    out[1:] = adx_arr
    return out


def bollinger_width(close: np.ndarray, period: int = 20, num_std: float = 2.0) -> np.ndarray:
    """Largeur relative des bandes : (haut − bas) / moyenne."""
    n = len(close)
    out = np.full(n, np.nan)
    if n < period:
        return out
    win = sliding_window_view(close, period)
    mean = win.mean(axis=1)
    std = win.std(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        width = (2.0 * num_std * std) / mean
    out[period - 1 :] = width
    return out


def rolling_percentile_rank(values: np.ndarray, window: int) -> np.ndarray:
    """Rang percentile (0–100) de values[i] parmi values[i-window+1 .. i]."""
    n = len(values)
    out = np.full(n, np.nan)
    if n < window:
        return out
    win = sliding_window_view(values, window)  # win[k] couvre [k .. k+window-1]
    last = win[:, -1][:, None]
    rank = (win <= last).sum(axis=1) - 1  # nb de valeurs strictement avant soi-même
    out[window - 1 :] = 100.0 * rank / (window - 1)
    return out


def rolling_percentile_value(values: np.ndarray, window: int, pct: float) -> np.ndarray:
    """Valeur du percentile `pct` sur la fenêtre glissante terminant à i (inclus)."""
    n = len(values)
    out = np.full(n, np.nan)
    if n < window:
        return out
    win = sliding_window_view(values, window)
    out[window - 1 :] = np.nanpercentile(win, pct, axis=1)
    return out


def hurst_rs(close: np.ndarray, window: int = 100, refresh_every: int = 5) -> np.ndarray:
    """Exposant de Hurst (méthode R/S simplifiée) sur fenêtre glissante.

    Recalculé toutes les `refresh_every` bougies (le régime varie lentement),
    la dernière valeur étant propagée entre deux recalculs — toujours causal.
    """
    n = len(close)
    out = np.full(n, np.nan)
    if n < window + 1:
        return out
    log_ret = np.diff(np.log(np.maximum(close, 1e-12)))
    # sous-fenêtres dyadiques pour la régression log(R/S) ~ H·log(taille)
    sizes = np.array([s for s in (8, 16, 32, 64, 128, 256) if s <= window - 1])
    if len(sizes) < 2:
        return out
    log_sizes = np.log(sizes.astype(float))
    last = np.nan
    for i in range(window, n):
        if (i - window) % refresh_every == 0:
            seg = log_ret[i - window : i]
            rs_vals = np.empty(len(sizes))
            for k, s in enumerate(sizes):
                m = (len(seg) // s) * s
                chunks = seg[len(seg) - m :].reshape(-1, s)
                mean = chunks.mean(axis=1, keepdims=True)
                dev = np.cumsum(chunks - mean, axis=1)
                r = dev.max(axis=1) - dev.min(axis=1)
                sd = chunks.std(axis=1)
                ok = sd > 1e-12
                rs_vals[k] = (r[ok] / sd[ok]).mean() if ok.any() else np.nan
            mask = np.isfinite(rs_vals) & (rs_vals > 0)
            if mask.sum() >= 2:
                slope = np.polyfit(log_sizes[mask], np.log(rs_vals[mask]), 1)[0]
                last = float(slope)
        out[i] = last
    return out
