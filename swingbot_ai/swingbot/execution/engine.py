"""Execution Engine : du signal risk-approuvé à la position protégée.

Responsabilités (section 7) : idempotence, envoi d'ordre, vérification SL
broker, re-sizing si le broker impose un stop plus large, transitions de la
machine d'états, et fermeture d'urgence si la protection échoue.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..constants import Direction, TradeState
from ..data.models import Instrument, Position, Signal
from ..journal.journal import Journal
from ..risk.sizing import SizingResult, compute_size
from ..trade.state_machine import TradeLifecycle
from .broker_base import Broker, OrderRequest, OrderResult


class ExecutionEngine:
    def __init__(self, broker: Broker, journal: Journal):
        self.broker = broker
        self.journal = journal

    def execute(self, signal: Signal, instrument: Instrument,
                lifecycle: TradeLifecycle, equity: float, risk_pct: float,
                account_currency: str, fx_rates: dict[str, float],
                spread_pips: float, slippage_stress_pips: float) -> Position | None:
        """Exécute un signal déjà RISK_APPROVED. Retourne la Position ou None.

        Le sizing est fait ICI, sur le stop broker RÉEL (principe 5) :
        1. lire la distance minimale broker ;
        2. élargir le stop si nécessaire — puis RE-VÉRIFIER le R:R ;
        3. sizing sur le stop final ;
        4. envoyer l'ordre avec clé idempotente ;
        5. vérifier la confirmation du SL, sinon fermeture d'urgence.
        """
        assert lifecycle.state == TradeState.RISK_APPROVED

        # 1-2. Stop broker réel.
        min_dist = self.broker.min_stop_distance(signal.symbol)
        stop = signal.stop_price
        entry = signal.entry_price
        if abs(entry - stop) < min_dist:
            if signal.direction == Direction.LONG:
                stop = entry - min_dist
            else:
                stop = entry + min_dist
            # R:R recalculé avec le stop élargi : refus si le R:R tombe
            # sous le minimum (principe 5.3.2).
            if signal.target_price is not None:
                reward = abs(signal.target_price - entry)
                new_rr = reward / abs(entry - stop) if abs(entry - stop) > 0 else 0
                if new_rr < 2.0:
                    tr = lifecycle.transition(TradeState.REJECTED,
                                              f"stop broker élargi => R:R {new_rr:.2f} < 2")
                    self.journal.log_transition(lifecycle.trade_id, tr)
                    return None

        # 3. Sizing sur stop réel.
        sizing: SizingResult = compute_size(
            instrument, signal.direction, entry, stop, equity, risk_pct,
            account_currency, fx_rates, spread_pips, slippage_stress_pips)
        if not sizing.ok:
            tr = lifecycle.transition(TradeState.REJECTED,
                                      f"sizing refusé: {sizing.details.get('error')}")
            self.journal.log_transition(lifecycle.trade_id, tr)
            return None

        # 4. Ordre idempotent.
        req = OrderRequest(
            idempotency_key=f"swing-{lifecycle.trade_id}",
            symbol=signal.symbol, direction=signal.direction,
            units=sizing.units, stop_price=stop,
            target_price=signal.target_price)
        tr = lifecycle.transition(TradeState.ORDER_SENT, "ordre envoyé",
                                  {"units": sizing.units, "stop": stop})
        self.journal.log_transition(lifecycle.trade_id, tr)

        result: OrderResult = self.broker.place_order(req)
        if not result.accepted:
            tr = lifecycle.transition(TradeState.ORDER_FAILED,
                                      f"ordre refusé: {result.error}")
            self.journal.log_transition(lifecycle.trade_id, tr)
            return None

        tr = lifecycle.transition(TradeState.BROKER_CONFIRMED, "deal accepté",
                                  {"deal_id": result.deal_id,
                                   "fill": result.fill_price})
        self.journal.log_transition(lifecycle.trade_id, tr)

        # 5. AUCUN ordre sans stop-loss broker confirmé (principe 1).
        if not result.stop_confirmed or result.confirmed_stop_price is None:
            tr = lifecycle.transition(TradeState.PROTECTION_FAILED,
                                      "SL non confirmé par le broker")
            self.journal.log_transition(lifecycle.trade_id, tr)
            if result.deal_id:
                self.broker.close_position(result.deal_id)
                tr = lifecycle.transition(TradeState.EMERGENCY_CLOSED,
                                          "fermeture d'urgence: position non protégée")
                self.journal.log_transition(lifecycle.trade_id, tr)
            return None

        fill = result.fill_price or entry
        confirmed_stop = result.confirmed_stop_price
        risk_r_unit = abs(fill - confirmed_stop)  # par unité, en prix
        position = Position(
            position_id=str(uuid.uuid4()),
            symbol=signal.symbol, direction=signal.direction,
            units=sizing.units, entry_price=fill,
            stop_price=confirmed_stop, target_price=signal.target_price,
            opened_ts=datetime.now(timezone.utc),
            risk_money=sizing.risk_money,
            risk_r_unit=risk_r_unit * sizing.units,
            broker_deal_id=result.deal_id)

        tr = lifecycle.transition(TradeState.OPEN, "position ouverte et protégée")
        self.journal.log_transition(lifecycle.trade_id, tr)
        self.journal.log_position_open(lifecycle.trade_id, position)
        return position
