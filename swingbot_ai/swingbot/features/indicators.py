"""Indicateurs techniques en Python pur : EMA, ATR, ADX, pente.

Implémentations volontairement explicites et testées unitairement
(section 16 : tests indicateurs obligatoires).
"""

from __future__ import annotations

from ..data.models import Candle


def ema(values: list[float], period: int) -> list[float | None]:
    """EMA classique. None tant que la fenêtre initiale (SMA) n'est pas pleine."""
    if period <= 0:
        raise ValueError("period doit être > 0")
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    k = 2.0 / (period + 1)
    sma = sum(values[:period]) / period
    out[period - 1] = sma
    prev = sma
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def true_range(candles: list[Candle]) -> list[float]:
    tr: list[float] = []
    for i, c in enumerate(candles):
        if i == 0:
            tr.append(c.high - c.low)
        else:
            pc = candles[i - 1].close
            tr.append(max(c.high - c.low, abs(c.high - pc), abs(c.low - pc)))
    return tr


def atr(candles: list[Candle], period: int = 14) -> list[float | None]:
    """ATR de Wilder (lissage RMA)."""
    tr = true_range(candles)
    out: list[float | None] = [None] * len(candles)
    if len(candles) < period:
        return out
    first = sum(tr[:period]) / period
    out[period - 1] = first
    prev = first
    for i in range(period, len(candles)):
        prev = (prev * (period - 1) + tr[i]) / period
        out[i] = prev
    return out


def adx(candles: list[Candle], period: int = 14) -> list[float | None]:
    """ADX de Wilder. Filtre de force de tendance optionnel (section 5.1)."""
    n = len(candles)
    out: list[float | None] = [None] * n
    if n < 2 * period + 1:
        return out

    plus_dm, minus_dm = [0.0], [0.0]
    tr = true_range(candles)
    for i in range(1, n):
        up = candles[i].high - candles[i - 1].high
        down = candles[i - 1].low - candles[i].low
        plus_dm.append(up if (up > down and up > 0) else 0.0)
        minus_dm.append(down if (down > up and down > 0) else 0.0)

    def wilder_smooth(vals: list[float]) -> list[float]:
        sm = [0.0] * n
        first = sum(vals[1:period + 1])
        sm[period] = first
        for i in range(period + 1, n):
            sm[i] = sm[i - 1] - sm[i - 1] / period + vals[i]
        return sm

    tr_s = wilder_smooth(tr)
    pdm_s = wilder_smooth(plus_dm)
    mdm_s = wilder_smooth(minus_dm)

    dx = [0.0] * n
    for i in range(period, n):
        if tr_s[i] <= 0:
            continue
        pdi = 100.0 * pdm_s[i] / tr_s[i]
        mdi = 100.0 * mdm_s[i] / tr_s[i]
        s = pdi + mdi
        dx[i] = 100.0 * abs(pdi - mdi) / s if s > 0 else 0.0

    first_adx = sum(dx[period:2 * period]) / period
    out[2 * period - 1] = first_adx
    prev = first_adx
    for i in range(2 * period, n):
        prev = (prev * (period - 1) + dx[i]) / period
        out[i] = prev
    return out


def slope(values: list[float | None], lookback: int = 5) -> float | None:
    """Pente simple sur `lookback` barres (dernière - ancienne) / lookback."""
    if len(values) < lookback + 1:
        return None
    a, b = values[-1], values[-1 - lookback]
    if a is None or b is None:
        return None
    return (a - b) / lookback
