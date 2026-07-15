"""Tests du Risk Engine : sizing, plafonds, corrélations, kill-switch.

Test de propriété central (section 16) : le risque ne dépasse JAMAIS le
plafond, quelles que soient les entrées.
"""

import random
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from swingbot.config import RiskLimits
from swingbot.constants import Direction
from swingbot.data.models import MAJORS, Position, Signal
from swingbot.risk.correlation import cluster_risk, rolling_correlation, worst_cluster
from swingbot.risk.killswitch import evaluate_triggers
from swingbot.risk.limits import check_candidate
from swingbot.risk.sizing import compute_size, convert_to_account

FX = {"EURUSD": 1.10, "GBPUSD": 1.27, "USDJPY": 148.0, "AUDUSD": 0.66,
      "USDCAD": 1.36}
NOW = datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc)  # mercredi


def make_position(symbol="EURUSD", direction=Direction.LONG, risk=50.0):
    return Position(
        position_id="p1", symbol=symbol, direction=direction, units=10_000,
        entry_price=1.10, stop_price=1.09, target_price=1.13,
        opened_ts=NOW, risk_money=risk, risk_r_unit=risk)


def make_signal(symbol="EURUSD"):
    return Signal(
        signal_id="s1", ts=NOW, symbol=symbol, direction=Direction.LONG,
        entry_price=1.10, stop_price=1.0920, target_price=1.1240,
        rr_expected=3.0, regime="bullish", score=0.7)


class TestSizing(unittest.TestCase):
    def test_property_risk_never_exceeds_budget(self):
        """Propriété : pour des entrées aléatoires, risk_money <= budget."""
        rng = random.Random(7)
        inst = MAJORS["EURUSD"]
        for _ in range(500):
            equity = rng.uniform(1_000, 100_000)
            risk_pct = rng.choice([0.25, 0.5])
            entry = rng.uniform(0.9, 1.4)
            stop = entry - rng.uniform(0.0005, 0.05)
            res = compute_size(inst, Direction.LONG, entry, stop, equity,
                               risk_pct, "EUR", FX,
                               spread_pips=rng.uniform(0, 3),
                               slippage_stress_pips=rng.uniform(0, 3),
                               swap_estimate_money_per_unit=rng.uniform(0, 1e-5))
            budget = equity * risk_pct / 100.0
            self.assertLessEqual(res.risk_money, budget * 1.0001,
                                 f"risque {res.risk_money} > budget {budget}")

    def test_zero_stop_distance_refused(self):
        inst = MAJORS["EURUSD"]
        res = compute_size(inst, Direction.LONG, 1.10, 1.10, 10_000, 0.5,
                           "EUR", FX)
        self.assertFalse(res.ok)

    def test_missing_fx_rate_abstains(self):
        inst = MAJORS["USDJPY"]  # quote JPY, compte EUR, pas de taux JPY
        res = compute_size(inst, Direction.LONG, 148.0, 147.0, 10_000, 0.5,
                           "EUR", {})
        self.assertFalse(res.ok)

    def test_conversion(self):
        self.assertAlmostEqual(convert_to_account(110, "USD", "EUR",
                                                  {"EURUSD": 1.10}), 100.0)
        self.assertAlmostEqual(convert_to_account(100, "EUR", "EUR", {}), 100.0)


class TestLimits(unittest.TestCase):
    def setUp(self):
        self.limits = RiskLimits()  # shadow/démo par défaut
        self.equity = 10_000.0

    def approve(self, signal, candidate, open_positions, **kw):
        return check_candidate(signal, candidate, open_positions, self.equity,
                               self.limits, kw.get("ks", False),
                               kw.get("daily", 0.0), kw.get("weekly", 0.0),
                               kw.get("now", NOW))

    def test_clean_candidate_approved(self):
        d = self.approve(make_signal(), make_position(risk=50), [])
        self.assertTrue(d.approved, d.reasons)

    def test_killswitch_blocks_everything(self):
        d = self.approve(make_signal(), make_position(risk=1), [], ks=True)
        self.assertFalse(d.approved)

    def test_max_positions(self):
        open_pos = [make_position(s, risk=10) for s in ("GBPUSD", "AUDUSD", "USDCAD")]
        d = self.approve(make_signal(), make_position(risk=10), open_pos)
        self.assertFalse(d.approved)

    def test_duplicate_symbol_blocked(self):
        d = self.approve(make_signal("EURUSD"), make_position(risk=10),
                         [make_position("EURUSD", risk=10)])
        self.assertFalse(d.approved)

    def test_per_trade_cap(self):
        d = self.approve(make_signal(), make_position(risk=51), [])  # > 0.5%
        self.assertFalse(d.approved)

    def test_cluster_cap_usd_common_exposure(self):
        # EURUSD long + GBPUSD long = double exposition USD (6.3).
        open_pos = [make_position("GBPUSD", risk=50)]
        d = self.approve(make_signal("EURUSD"), make_position(risk=50), open_pos)
        self.assertFalse(d.approved)
        self.assertTrue(any("cluster" in r for r in d.reasons), d.reasons)

    def test_friday_evening_blocked(self):
        friday_evening = datetime(2026, 7, 17, 16, 0, tzinfo=timezone.utc)
        d = self.approve(make_signal(), make_position(risk=10), [],
                         now=friday_evening)
        self.assertFalse(d.approved)

    def test_daily_loss_cap(self):
        d = self.approve(make_signal(), make_position(risk=10), [], daily=-1.6)
        self.assertFalse(d.approved)


class TestCorrelation(unittest.TestCase):
    def test_usd_cluster_aggregation(self):
        pos = [make_position("EURUSD", Direction.LONG, 50),
               make_position("GBPUSD", Direction.LONG, 50)]
        clusters = cluster_risk(pos)
        self.assertAlmostEqual(clusters["USD"], 100.0)  # exposition commune

    def test_offsetting_positions(self):
        pos = [make_position("EURUSD", Direction.LONG, 50),
               make_position("GBPUSD", Direction.SHORT, 50)]
        clusters = cluster_risk(pos)
        self.assertAlmostEqual(clusters["USD"], 0.0)

    def test_rolling_correlation_perfect(self):
        a = [0.01, -0.02, 0.03, -0.01] * 10
        self.assertAlmostEqual(rolling_correlation(a, a), 1.0)
        inv = [-x for x in a]
        self.assertAlmostEqual(rolling_correlation(a, inv), -1.0)


class TestKillSwitch(unittest.TestCase):
    def test_drawdown_trigger(self):
        limits = RiskLimits()
        triggers = evaluate_triggers(9_100, 10_000, 0, 0, limits)
        self.assertTrue(any("drawdown" in t for t in triggers))

    def test_no_trigger_when_healthy(self):
        limits = RiskLimits()
        self.assertEqual(evaluate_triggers(10_000, 10_000, 0, 0, limits), [])

    def test_unprotected_position_trigger(self):
        limits = RiskLimits()
        triggers = evaluate_triggers(10_000, 10_000, 0, 0, limits,
                                     sl_confirmed_everywhere=False)
        self.assertTrue(any("stop-loss" in t for t in triggers))


if __name__ == "__main__":
    unittest.main()
