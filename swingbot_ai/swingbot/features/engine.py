"""Feature Engine : calcule et regroupe les features multi-timeframes.

Entrées : H4 brut. Le Daily et le Weekly sont resamplés en interne.
Toutes les features sont calculées sur bougies CLÔTURÉES uniquement.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..constants import Timeframe
from ..data.models import Candle
from ..data.provider import resample
from . import indicators as ind
from .structure import Pivot, classify_structure, find_pivots, pivots_known_at


@dataclass
class FeatureSet:
    """Photographie des features au moment d'une clôture H4."""
    h4: list[Candle]
    daily: list[Candle]          # clôturées uniquement
    weekly: list[Candle]         # clôturées uniquement
    ema20_h4: list[float | None] = field(default_factory=list)
    ema50_h4: list[float | None] = field(default_factory=list)
    ema50_d: list[float | None] = field(default_factory=list)
    ema200_d: list[float | None] = field(default_factory=list)
    atr_h4: list[float | None] = field(default_factory=list)
    atr_d: list[float | None] = field(default_factory=list)
    adx_d: list[float | None] = field(default_factory=list)
    pivots_h4: list[Pivot] = field(default_factory=list)
    pivots_d: list[Pivot] = field(default_factory=list)

    def daily_structure(self) -> str:
        known = pivots_known_at(self.pivots_d, len(self.daily) - 1)
        return classify_structure(known)

    def h4_pivots_known(self) -> list[Pivot]:
        return pivots_known_at(self.pivots_h4, len(self.h4) - 1)


def compute_features(h4: list[Candle], ema_fast: int = 20, ema_mid: int = 50,
                     ema_slow: int = 200, atr_period: int = 14,
                     adx_period: int = 14, pivot_lookback: int = 5) -> FeatureSet:
    """Calcule toutes les features à partir d'une série H4 clôturée."""
    daily_all = resample(h4, Timeframe.D1)
    weekly_all = resample(h4, Timeframe.W1)
    # On écarte la dernière période si elle est incomplète (pas de décision
    # sur bougie en formation).
    daily = [c for c in daily_all if c.complete]
    weekly = [c for c in weekly_all if c.complete]

    closes_h4 = [c.close for c in h4]
    closes_d = [c.close for c in daily]

    return FeatureSet(
        h4=h4,
        daily=daily,
        weekly=weekly,
        ema20_h4=ind.ema(closes_h4, ema_fast),
        ema50_h4=ind.ema(closes_h4, ema_mid),
        ema50_d=ind.ema(closes_d, ema_mid),
        ema200_d=ind.ema(closes_d, ema_slow),
        atr_h4=ind.atr(h4, atr_period),
        atr_d=ind.atr(daily, atr_period),
        adx_d=ind.adx(daily, adx_period),
        pivots_h4=find_pivots(h4, pivot_lookback),
        pivots_d=find_pivots(daily, pivot_lookback),
    )
