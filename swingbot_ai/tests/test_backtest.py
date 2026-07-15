"""Tests du backtester : coûts, gaps, anti-lookahead, métriques, Monte-Carlo."""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from swingbot.backtest.costs import CostModel
from swingbot.backtest.engine import run_backtest
from swingbot.backtest.metrics import Gates, check_gates, compute_metrics
from swingbot.backtest.montecarlo import montecarlo_drawdown
from swingbot.data.provider import generate_synthetic_h4, resample
from swingbot.data.quality import check_series
from swingbot.constants import Timeframe
from swingbot.strategy.swing_pullback import StrategyParams


def synthetic(bars=3000, seed=42):
    return generate_synthetic_h4("EURUSD",
                                 datetime(2019, 1, 1, tzinfo=timezone.utc),
                                 bars, seed=seed)


class TestCostModel(unittest.TestCase):
    def test_triple_swap_wednesday(self):
        cm = CostModel(swap_long_pips_per_day=-0.5, triple_swap_weekday=2, seed=1)
        self.assertAlmostEqual(cm.swap_pips_for_day(True, 2), -1.5)
        self.assertAlmostEqual(cm.swap_pips_for_day(True, 3), -0.5)

    def test_stress_multiplier_never_improves(self):
        cm = CostModel(swap_long_pips_per_day=-0.5, stress_multiplier=1.5, seed=1)
        self.assertAlmostEqual(cm.swap_pips_for_day(True, 3), -0.75)
        cm_pos = CostModel(swap_short_pips_per_day=0.3, stress_multiplier=1.5, seed=1)
        self.assertAlmostEqual(cm_pos.swap_pips_for_day(False, 3), 0.3)

    def test_slippage_bounds(self):
        cm = CostModel(slippage_pips_max=1.0, seed=5)
        for _ in range(100):
            s = cm.slippage_pips()
            self.assertGreaterEqual(s, 0.0)
            self.assertLessEqual(s, 1.0)


class TestBacktest(unittest.TestCase):
    def test_runs_and_costs_accounted(self):
        candles = synthetic(3000)
        res = run_backtest("EURUSD", candles, StrategyParams(),
                           CostModel(seed=42), 10_000)
        # La tuyauterie doit produire une courbe d'equity complète.
        self.assertGreater(len(res.equity_curve), 0)
        for t in res.trades:
            self.assertGreaterEqual(t.costs_money, 0.0)
            # PnL = brut + swap - coûts, donc net <= brut quand swap <= 0.
            self.assertLessEqual(abs(t.pnl_r), 60)  # sanité

    def test_deterministic_same_seed(self):
        candles = synthetic(2000)
        r1 = run_backtest("EURUSD", candles, StrategyParams(), CostModel(seed=9), 10_000)
        r2 = run_backtest("EURUSD", candles, StrategyParams(), CostModel(seed=9), 10_000)
        self.assertEqual([t.pnl_money for t in r1.trades],
                         [t.pnl_money for t in r2.trades])

    def test_losses_bounded_near_1r(self):
        """Hors gap, une perte au stop ne doit pas dépasser ~1R + coûts."""
        candles = synthetic(3000)
        res = run_backtest("EURUSD", candles, StrategyParams(), CostModel(seed=42), 10_000)
        for t in res.trades:
            if t.exit_reason == "stop":
                self.assertGreater(t.pnl_r, -1.6, f"perte anormale: {t}")


class TestResample(unittest.TestCase):
    def test_last_period_incomplete(self):
        candles = synthetic(500)
        daily = resample(candles, Timeframe.D1)
        self.assertFalse(daily[-1].complete)
        self.assertTrue(all(c.complete for c in daily[:-1]))

    def test_daily_ohlc_consistent(self):
        candles = synthetic(500)
        for d in resample(candles, Timeframe.D1):
            self.assertGreaterEqual(d.high, max(d.open, d.close))
            self.assertLessEqual(d.low, min(d.open, d.close))


class TestQuality(unittest.TestCase):
    def test_clean_series_ok(self):
        candles = synthetic(500)
        self.assertTrue(check_series(candles, Timeframe.H4).ok)

    def test_gap_detected(self):
        candles = synthetic(500)
        broken = candles[:300] + candles[350:]  # trou de 50 bougies
        report = check_series(broken, Timeframe.H4)
        self.assertFalse(report.ok)

    def test_insufficient_history(self):
        self.assertFalse(check_series(synthetic(50), Timeframe.H4).ok)


class TestGatesAndMC(unittest.TestCase):
    def test_gates_no_go_on_few_trades(self):
        metrics = {"profit_factor": 2.0, "expectancy_r": 0.5,
                   "n_trades": 10, "max_drawdown_pct": 2.0}
        ok, fails = check_gates(metrics, Gates())
        self.assertFalse(ok)
        self.assertTrue(any("trades" in f for f in fails))

    def test_montecarlo_percentiles_ordered(self):
        pnls = [100, -50, 80, -60, 120, -40] * 30
        mc = montecarlo_drawdown(pnls, 10_000, runs=200)
        self.assertLessEqual(mc["p50"], mc["p95"])
        self.assertLessEqual(mc["p95"], mc["p99"])


if __name__ == "__main__":
    unittest.main()
