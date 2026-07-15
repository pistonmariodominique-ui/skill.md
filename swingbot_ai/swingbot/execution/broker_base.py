"""Interface broker abstraite.

Contrat commun à PaperBroker (shadow/démo interne) et CapitalComBroker.
Règle absolue : place_order N'EST PAS terminé tant que le stop-loss n'est
pas CONFIRMÉ par le broker (principe 1). Un ordre sans SL confirmé doit
être traité comme PROTECTION_FAILED et fermé d'urgence.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..constants import Direction


@dataclass
class OrderRequest:
    idempotency_key: str
    symbol: str
    direction: Direction
    units: float
    stop_price: float
    target_price: float | None = None
    order_type: str = "market"          # "market" | "limit"
    limit_price: float | None = None


@dataclass
class OrderResult:
    accepted: bool
    deal_id: str | None = None
    fill_price: float | None = None
    confirmed_stop_price: float | None = None   # stop RÉEL accepté par le broker
    stop_confirmed: bool = False
    error: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class BrokerPosition:
    deal_id: str
    symbol: str
    direction: Direction
    units: float
    entry_price: float
    stop_price: float | None
    target_price: float | None
    swap_accrued: float = 0.0


class Broker(ABC):
    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def min_stop_distance(self, symbol: str) -> float:
        """Distance minimale de stop en unités de prix (lecture broker)."""

    @abstractmethod
    def place_order(self, req: OrderRequest) -> OrderResult: ...

    @abstractmethod
    def modify_stop(self, deal_id: str, new_stop: float) -> bool: ...

    @abstractmethod
    def close_position(self, deal_id: str) -> OrderResult: ...

    @abstractmethod
    def list_positions(self) -> list[BrokerPosition]: ...

    @abstractmethod
    def account_equity(self) -> float: ...

    @abstractmethod
    def transactions_since(self, iso_ts: str) -> list[dict]:
        """Historique des transactions pour la réconciliation."""
