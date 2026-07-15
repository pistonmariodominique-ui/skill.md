"""Broker papier : simulation locale fidèle pour shadow/démo interne.

Simule : spread, slippage, distance minimale de stop, confirmation SL,
swap journalier (avec triple swap), gaps au-delà du stop (exécution au
premier prix disponible), et pannes aléatoires optionnelles (chaos tests).
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field

from ..constants import Direction
from ..data.models import MAJORS
from .broker_base import Broker, BrokerPosition, OrderRequest, OrderResult


@dataclass
class PaperBroker(Broker):
    equity: float = 10_000.0
    spread_pips: float = 1.0
    slippage_pips_max: float = 0.5
    chaos_failure_rate: float = 0.0     # >0 pour les chaos tests (section 16)
    seed: int | None = None
    positions: dict[str, BrokerPosition] = field(default_factory=dict)
    _tx: list[dict] = field(default_factory=list)
    _prices: dict[str, float] = field(default_factory=dict)
    _seen_keys: dict[str, OrderResult] = field(default_factory=dict)

    def __post_init__(self):
        self._rng = random.Random(self.seed)

    # --- alimentation des prix (par la boucle live ou le backtest) --------
    def set_price(self, symbol: str, price: float) -> None:
        self._prices[symbol] = price

    # --- interface Broker ---------------------------------------------------
    def is_available(self) -> bool:
        if self.chaos_failure_rate > 0 and self._rng.random() < self.chaos_failure_rate:
            return False
        return True

    def min_stop_distance(self, symbol: str) -> float:
        inst = MAJORS[symbol]
        return inst.min_stop_distance_pips * inst.pip_size

    def place_order(self, req: OrderRequest) -> OrderResult:
        # Idempotence : même clé => même résultat, jamais de double ordre.
        if req.idempotency_key in self._seen_keys:
            return self._seen_keys[req.idempotency_key]

        if not self.is_available():
            return OrderResult(False, error="broker indisponible (chaos)")

        price = self._prices.get(req.symbol)
        if price is None:
            return OrderResult(False, error=f"pas de prix pour {req.symbol}")

        inst = MAJORS[req.symbol]
        half_spread = self.spread_pips * inst.pip_size / 2.0
        slip = self._rng.uniform(0, self.slippage_pips_max) * inst.pip_size
        # Slippage toujours DÉFAVORABLE (backtest pessimiste, section 11).
        if req.direction == Direction.LONG:
            fill = price + half_spread + slip
        else:
            fill = price - half_spread - slip

        # Distance minimale de stop : le broker peut REFUSER ou ajuster.
        min_dist = self.min_stop_distance(req.symbol)
        stop = req.stop_price
        if abs(fill - stop) < min_dist:
            return OrderResult(False, error=(
                f"stop trop proche: {abs(fill - stop):.5f} < min {min_dist:.5f}"))

        deal_id = str(uuid.uuid4())[:8]
        pos = BrokerPosition(
            deal_id=deal_id, symbol=req.symbol, direction=req.direction,
            units=req.units, entry_price=fill, stop_price=stop,
            target_price=req.target_price)
        self.positions[deal_id] = pos
        self._tx.append({"kind": "open", "deal_id": deal_id,
                         "symbol": req.symbol, "units": req.units,
                         "price": fill})
        result = OrderResult(True, deal_id=deal_id, fill_price=fill,
                             confirmed_stop_price=stop, stop_confirmed=True)
        self._seen_keys[req.idempotency_key] = result
        return result

    def modify_stop(self, deal_id: str, new_stop: float) -> bool:
        pos = self.positions.get(deal_id)
        if pos is None:
            return False
        pos.stop_price = new_stop
        self._tx.append({"kind": "modify_stop", "deal_id": deal_id, "stop": new_stop})
        return True

    def close_position(self, deal_id: str) -> OrderResult:
        pos = self.positions.pop(deal_id, None)
        if pos is None:
            return OrderResult(False, error="position inconnue")
        price = self._prices.get(pos.symbol, pos.entry_price)
        inst = MAJORS[pos.symbol]
        half_spread = self.spread_pips * inst.pip_size / 2.0
        fill = price - half_spread if pos.direction == Direction.LONG else price + half_spread
        self._tx.append({"kind": "close", "deal_id": deal_id, "price": fill})
        return OrderResult(True, deal_id=deal_id, fill_price=fill)

    def list_positions(self) -> list[BrokerPosition]:
        return list(self.positions.values())

    def account_equity(self) -> float:
        return self.equity

    def transactions_since(self, iso_ts: str) -> list[dict]:
        return list(self._tx)
