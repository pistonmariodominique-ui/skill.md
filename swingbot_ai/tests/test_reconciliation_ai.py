"""Tests réconciliation + validation du schéma IA."""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from swingbot.ai.analyst import validate_report
from swingbot.constants import Direction
from swingbot.data.models import Position
from swingbot.execution.broker_base import OrderRequest
from swingbot.execution.paper_broker import PaperBroker
from swingbot.reconciliation.reconciler import reconcile

NOW = datetime(2026, 7, 15, tzinfo=timezone.utc)


def open_broker_position(broker, key="k1"):
    broker.set_price("EURUSD", 1.1000)
    r = broker.place_order(OrderRequest(key, "EURUSD", Direction.LONG,
                                        10_000, 1.0900))
    return r


class TestReconciliation(unittest.TestCase):
    def test_synced(self):
        broker = PaperBroker(seed=1)
        r = open_broker_position(broker)
        local = [Position("p1", "EURUSD", Direction.LONG, 10_000, r.fill_price,
                          1.0900, None, NOW, 50, 50, broker_deal_id=r.deal_id)]
        self.assertTrue(reconcile(local, broker).ok)

    def test_unknown_at_broker(self):
        broker = PaperBroker(seed=1)
        open_broker_position(broker)
        report = reconcile([], broker)
        self.assertFalse(report.ok)
        self.assertEqual(len(report.unknown_at_broker), 1)

    def test_missing_at_broker(self):
        broker = PaperBroker(seed=1)
        local = [Position("p1", "EURUSD", Direction.LONG, 10_000, 1.10,
                          1.09, None, NOW, 50, 50, broker_deal_id="fantome")]
        report = reconcile(local, broker)
        self.assertFalse(report.ok)
        self.assertEqual(len(report.missing_at_broker), 1)

    def test_stop_mismatch(self):
        broker = PaperBroker(seed=1)
        r = open_broker_position(broker)
        broker.modify_stop(r.deal_id, 1.0950)  # modifié côté broker
        local = [Position("p1", "EURUSD", Direction.LONG, 10_000, r.fill_price,
                          1.0900, None, NOW, 50, 50, broker_deal_id=r.deal_id)]
        report = reconcile(local, broker)
        self.assertFalse(report.ok)
        self.assertEqual(len(report.stop_mismatches), 1)


class TestAISchema(unittest.TestCase):
    def valid(self):
        return {"market_regime": "bullish", "setup_quality": 7,
                "contradictions": [], "event_risks": ["FOMC"],
                "explanation": "ok", "confidence": 0.8}

    def test_valid_accepted(self):
        report = validate_report(self.valid())
        self.assertIsNotNone(report)
        self.assertEqual(report.market_regime, "bullish")

    def test_invalid_regime_rejected(self):
        raw = self.valid()
        raw["market_regime"] = "to_the_moon"
        self.assertIsNone(validate_report(raw))

    def test_out_of_range_confidence_rejected(self):
        raw = self.valid()
        raw["confidence"] = 1.7
        self.assertIsNone(validate_report(raw))

    def test_missing_field_rejected(self):
        raw = self.valid()
        del raw["setup_quality"]
        self.assertIsNone(validate_report(raw))


if __name__ == "__main__":
    unittest.main()
