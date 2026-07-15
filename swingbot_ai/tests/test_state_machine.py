"""Tests de la machine d'états et de l'idempotence d'exécution."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from swingbot.constants import Direction, TradeState
from swingbot.execution.broker_base import OrderRequest
from swingbot.execution.paper_broker import PaperBroker
from swingbot.trade.state_machine import IllegalTransition, TradeLifecycle


class TestStateMachine(unittest.TestCase):
    def test_happy_path(self):
        lc = TradeLifecycle.new("EURUSD", "1.0.0")
        for state in (TradeState.VALIDATED, TradeState.RISK_APPROVED,
                      TradeState.ORDER_SENT, TradeState.BROKER_CONFIRMED,
                      TradeState.OPEN, TradeState.CLOSED, TradeState.RECONCILED):
            lc.transition(state, "test")
        self.assertTrue(lc.is_terminal)
        self.assertEqual(len(lc.transitions), 7)

    def test_illegal_transition_raises(self):
        lc = TradeLifecycle.new("EURUSD", "1.0.0")
        with self.assertRaises(IllegalTransition):
            lc.transition(TradeState.OPEN, "saut interdit")

    def test_terminal_state_frozen(self):
        lc = TradeLifecycle.new("EURUSD", "1.0.0")
        lc.transition(TradeState.REJECTED, "refus")
        with self.assertRaises(IllegalTransition):
            lc.transition(TradeState.VALIDATED, "résurrection interdite")

    def test_secrets_sanitized_in_payload(self):
        lc = TradeLifecycle.new("EURUSD", "1.0.0")
        tr = lc.transition(TradeState.VALIDATED, "ok",
                           {"deal": "d1", "api_key": "SECRET", "CST": "tok"})
        self.assertEqual(tr.broker_payload["api_key"], "***")
        self.assertEqual(tr.broker_payload["CST"], "***")
        self.assertEqual(tr.broker_payload["deal"], "d1")


class TestPaperBrokerIdempotence(unittest.TestCase):
    def test_same_key_no_double_order(self):
        broker = PaperBroker(seed=1)
        broker.set_price("EURUSD", 1.1000)
        req = OrderRequest("key-1", "EURUSD", Direction.LONG, 10_000, 1.0900)
        r1 = broker.place_order(req)
        r2 = broker.place_order(req)  # retry réseau simulé
        self.assertTrue(r1.accepted)
        self.assertEqual(r1.deal_id, r2.deal_id)
        self.assertEqual(len(broker.positions), 1)

    def test_stop_too_close_rejected(self):
        broker = PaperBroker(seed=1)
        broker.set_price("EURUSD", 1.1000)
        req = OrderRequest("key-2", "EURUSD", Direction.LONG, 10_000, 1.09999)
        r = broker.place_order(req)
        self.assertFalse(r.accepted)
        self.assertIn("stop trop proche", r.error)

    def test_slippage_always_adverse(self):
        broker = PaperBroker(seed=3, spread_pips=1.0, slippage_pips_max=1.0)
        broker.set_price("EURUSD", 1.1000)
        r = broker.place_order(OrderRequest("k", "EURUSD", Direction.LONG,
                                            10_000, 1.0900))
        self.assertGreaterEqual(r.fill_price, 1.1000)  # jamais mieux que le mid


if __name__ == "__main__":
    unittest.main()
