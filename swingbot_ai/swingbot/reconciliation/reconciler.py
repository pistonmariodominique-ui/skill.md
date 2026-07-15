"""Réconciliation broker <-> état interne (section 7).

Tout écart non expliqué => DESYNC => kill-switch. La vérité est TOUJOURS
côté broker : l'état interne s'aligne, jamais l'inverse.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..data.models import Position
from ..execution.broker_base import Broker, BrokerPosition


@dataclass
class ReconciliationReport:
    ok: bool
    missing_at_broker: list[str] = field(default_factory=list)   # connu ici, absent broker
    unknown_at_broker: list[str] = field(default_factory=list)   # présent broker, inconnu ici
    unprotected: list[str] = field(default_factory=list)         # position broker sans SL
    stop_mismatches: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.ok:
            return "réconciliation OK"
        parts = []
        if self.missing_at_broker:
            parts.append(f"absentes broker: {self.missing_at_broker}")
        if self.unknown_at_broker:
            parts.append(f"inconnues localement: {self.unknown_at_broker}")
        if self.unprotected:
            parts.append(f"SANS STOP: {self.unprotected}")
        if self.stop_mismatches:
            parts.append(f"stops divergents: {self.stop_mismatches}")
        return "; ".join(parts)


def reconcile(local_positions: list[Position], broker: Broker,
              stop_tolerance: float = 1e-4) -> ReconciliationReport:
    broker_positions: list[BrokerPosition] = broker.list_positions()
    by_deal = {bp.deal_id: bp for bp in broker_positions}
    local_deals = {p.broker_deal_id for p in local_positions if p.broker_deal_id}

    report = ReconciliationReport(ok=True)

    for p in local_positions:
        if p.broker_deal_id and p.broker_deal_id not in by_deal:
            report.missing_at_broker.append(f"{p.symbol}/{p.broker_deal_id}")
        elif p.broker_deal_id:
            bp = by_deal[p.broker_deal_id]
            if bp.stop_price is None:
                report.unprotected.append(f"{p.symbol}/{p.broker_deal_id}")
            elif abs(bp.stop_price - p.stop_price) > stop_tolerance:
                report.stop_mismatches.append(
                    f"{p.symbol}: local {p.stop_price} vs broker {bp.stop_price}")

    for bp in broker_positions:
        if bp.deal_id not in local_deals:
            report.unknown_at_broker.append(f"{bp.symbol}/{bp.deal_id}")
        # Même une position "connue" doit être protégée — déjà vérifié
        # au-dessus, mais une position inconnue sans stop est critique.
        elif bp.stop_price is None and f"{bp.symbol}/{bp.deal_id}" not in report.unprotected:
            report.unprotected.append(f"{bp.symbol}/{bp.deal_id}")

    report.ok = not (report.missing_at_broker or report.unknown_at_broker
                     or report.unprotected or report.stop_mismatches)
    return report
