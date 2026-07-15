"""Détection de régime de marché Daily (section 5.1).

- Haussier : clôture Daily > EMA200, EMA50 ascendante, structure HH/HL.
- Baissier : clôture Daily < EMA200, EMA50 descendante, structure LH/LL.
- Neutre/range : conditions contradictoires => aucune entrée de tendance.
"""

from __future__ import annotations

from ..constants import Regime
from ..features.engine import FeatureSet
from ..features import indicators as ind


def detect_regime(fs: FeatureSet, adx_min: float = 0.0) -> tuple[Regime, list[str]]:
    reasons: list[str] = []
    if not fs.daily or fs.ema200_d[-1] is None or fs.ema50_d[-1] is None:
        return Regime.UNCERTAIN, ["indicateurs Daily non disponibles"]

    close_d = fs.daily[-1].close
    ema200 = fs.ema200_d[-1]
    ema50_slope = ind.slope(fs.ema50_d, lookback=5)
    structure = fs.daily_structure()

    if adx_min > 0:
        adx_val = fs.adx_d[-1]
        if adx_val is None or adx_val < adx_min:
            reasons.append(f"ADX Daily {adx_val} < seuil {adx_min}")
            return Regime.RANGE, reasons

    above = close_d > ema200
    below = close_d < ema200
    up_slope = ema50_slope is not None and ema50_slope > 0
    down_slope = ema50_slope is not None and ema50_slope < 0

    if above and up_slope and structure == "up":
        reasons.append(f"clôture D {close_d:.5f} > EMA200 {ema200:.5f}, "
                       f"EMA50 ascendante, structure HH/HL")
        return Regime.BULLISH, reasons
    if below and down_slope and structure == "down":
        reasons.append(f"clôture D {close_d:.5f} < EMA200 {ema200:.5f}, "
                       f"EMA50 descendante, structure LH/LL")
        return Regime.BEARISH, reasons

    reasons.append(f"conditions contradictoires (close>{'EMA200' if above else '<EMA200'}, "
                   f"pente EMA50 {'up' if up_slope else 'down/flat'}, structure {structure})")
    return Regime.RANGE, reasons


def weekly_not_opposed(fs: FeatureSet, direction_bullish: bool) -> bool:
    """Tendance Weekly alignée ou non opposée (setup 5.2.1).

    Weekly opposée = clôture Weekly sous/dessus son EMA50 dans le sens
    contraire de la position envisagée.
    """
    if len(fs.weekly) < 55:
        return True  # pas assez d'historique weekly : on ne bloque pas sur ce seul critère
    closes_w = [c.close for c in fs.weekly]
    ema50_w = ind.ema(closes_w, 50)[-1]
    if ema50_w is None:
        return True
    if direction_bullish:
        return closes_w[-1] >= ema50_w
    return closes_w[-1] <= ema50_w
