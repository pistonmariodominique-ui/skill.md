"""Modèle de coûts du backtest (section 11) : spread variable, slippage
aléatoire et défavorable, swap journalier + triple swap, commission."""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class CostModel:
    spread_pips_base: float = 1.0
    spread_pips_stress: float = 2.5
    slippage_pips_max: float = 1.0
    commission_per_lot: float = 0.0
    swap_long_pips_per_day: float = -0.55
    swap_short_pips_per_day: float = -0.25
    triple_swap_weekday: int = 2        # mercredi (roll du weekend T+2)
    stress_multiplier: float = 1.0      # x1.5 pour le test de robustesse
    seed: int | None = None

    def __post_init__(self):
        self._rng = random.Random(self.seed)

    def spread_pips(self, high_vol: bool = False) -> float:
        base = self.spread_pips_stress if high_vol else self.spread_pips_base
        return base * self.stress_multiplier

    def slippage_pips(self) -> float:
        """Slippage aléatoire, toujours défavorable (0..max)."""
        return self._rng.uniform(0, self.slippage_pips_max) * self.stress_multiplier

    def swap_pips_for_day(self, is_long: bool, weekday: int) -> float:
        per_day = self.swap_long_pips_per_day if is_long else self.swap_short_pips_per_day
        mult = 3.0 if weekday == self.triple_swap_weekday else 1.0
        # Le swap est un coût : le multiplicateur de stress n'améliore
        # jamais un swap positif.
        swap = per_day * mult
        if swap < 0:
            swap *= self.stress_multiplier
        return swap
