"""Modèles de données de base : bougies, instruments, signaux, positions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..constants import Direction, Timeframe


@dataclass(frozen=True)
class Candle:
    """Bougie OHLCV clôturée, timestamp UTC = ouverture de la bougie."""
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    timeframe: Timeframe = Timeframe.H4
    complete: bool = True

    def __post_init__(self):
        if self.ts.tzinfo is None:
            object.__setattr__(self, "ts", self.ts.replace(tzinfo=timezone.utc))


@dataclass(frozen=True)
class Instrument:
    """Métadonnées broker d'un instrument (section 7, Market Data)."""
    symbol: str                      # ex: EURUSD
    base: str                        # EUR
    quote: str                       # USD
    pip_size: float = 0.0001         # 0.01 pour les paires JPY
    lot_size: float = 100_000.0      # unités par lot
    min_stop_distance_pips: float = 5.0
    typical_spread_pips: float = 1.0

    @property
    def epic(self) -> str:
        """Identifiant Capital.com (héritage ForexBot)."""
        return self.symbol

    def pip_value_quote(self, units: float) -> float:
        """Valeur d'un pip en devise de cotation pour `units` unités."""
        return units * self.pip_size


MAJORS: dict[str, Instrument] = {
    "EURUSD": Instrument("EURUSD", "EUR", "USD", 0.0001, 100_000, 5, 0.8),
    "GBPUSD": Instrument("GBPUSD", "GBP", "USD", 0.0001, 100_000, 6, 1.2),
    "USDJPY": Instrument("USDJPY", "USD", "JPY", 0.01, 100_000, 5, 0.9),
    "AUDUSD": Instrument("AUDUSD", "AUD", "USD", 0.0001, 100_000, 5, 1.0),
    "USDCAD": Instrument("USDCAD", "USD", "CAD", 0.0001, 100_000, 5, 1.4),
}


@dataclass
class Signal:
    """Signal déterministe produit par le Strategy Engine (section 7)."""
    signal_id: str
    ts: datetime
    symbol: str
    direction: Direction
    entry_price: float
    stop_price: float
    target_price: float | None
    rr_expected: float
    regime: str
    score: float
    reasons: list[str] = field(default_factory=list)
    abstain_reasons: list[str] = field(default_factory=list)
    strategy_version: str = "1.0.0"
    expires_after_bars: int = 2

    @property
    def is_actionable(self) -> bool:
        return not self.abstain_reasons

    @property
    def stop_distance(self) -> float:
        return abs(self.entry_price - self.stop_price)


@dataclass
class Position:
    """Position ouverte, suivie par le Risk Engine et la réconciliation."""
    position_id: str
    symbol: str
    direction: Direction
    units: float
    entry_price: float
    stop_price: float
    target_price: float | None
    opened_ts: datetime
    risk_money: float
    risk_r_unit: float               # valeur monétaire de 1R
    swap_accrued: float = 0.0
    broker_deal_id: str | None = None
    partial_taken: bool = False
    breakeven_moved: bool = False

    def unrealized_r(self, price: float) -> float:
        if self.risk_r_unit <= 0:
            return 0.0
        sign = 1.0 if self.direction == Direction.LONG else -1.0
        pnl = sign * (price - self.entry_price) * self.units
        return pnl / self.risk_r_unit
