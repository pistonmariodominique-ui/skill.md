"""Tests unitaires des indicateurs (section 16)."""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from swingbot.constants import Timeframe
from swingbot.data.models import Candle
from swingbot.features.indicators import adx, atr, ema, slope
from swingbot.features.structure import classify_structure, find_pivots, pivots_known_at


def make_candles(closes, spread=0.001):
    ts = datetime(2024, 1, 2, tzinfo=timezone.utc)
    out = []
    for i, c in enumerate(closes):
        o = closes[i - 1] if i > 0 else c
        out.append(Candle(ts=ts + timedelta(hours=4 * i), open=o,
                          high=max(o, c) + spread, low=min(o, c) - spread,
                          close=c, timeframe=Timeframe.H4))
    return out


class TestEMA(unittest.TestCase):
    def test_constant_series(self):
        values = [5.0] * 50
        result = ema(values, 10)
        self.assertIsNone(result[8])
        for v in result[9:]:
            self.assertAlmostEqual(v, 5.0)

    def test_seed_is_sma(self):
        values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        result = ema(values, 5)
        self.assertAlmostEqual(result[4], 3.0)  # SMA des 5 premiers

    def test_rising_series_lags_below(self):
        values = list(range(1, 101))
        result = ema([float(v) for v in values], 20)
        self.assertLess(result[-1], 100.0)
        self.assertGreater(result[-1], 80.0)

    def test_invalid_period(self):
        with self.assertRaises(ValueError):
            ema([1.0], 0)


class TestATR(unittest.TestCase):
    def test_constant_range(self):
        candles = make_candles([1.0] * 30, spread=0.005)
        result = atr(candles, 14)
        self.assertAlmostEqual(result[-1], 0.01, places=4)

    def test_none_before_period(self):
        candles = make_candles([1.0] * 30)
        self.assertIsNone(atr(candles, 14)[12])


class TestADX(unittest.TestCase):
    def test_trending_gt_flat(self):
        import random
        rng = random.Random(11)
        trend = make_candles([1.0 + i * 0.01 for i in range(120)])
        walk, price = [], 1.0
        for _ in range(120):
            price += rng.gauss(0, 0.004)
            walk.append(price)
        flat = make_candles(walk)
        adx_trend = adx(trend, 14)[-1]
        adx_flat = adx(flat, 14)[-1]
        self.assertIsNotNone(adx_trend)
        self.assertGreater(adx_trend, adx_flat)


class TestStructure(unittest.TestCase):
    def test_pivot_confirmation_no_lookahead(self):
        closes = [1.0, 1.01, 1.02, 1.05, 1.02, 1.01, 1.0, 0.99, 0.98, 1.0, 1.01, 1.02]
        candles = make_candles(closes, spread=0.0)
        pivots = find_pivots(candles, lookback=3)
        for p in pivots:
            self.assertEqual(p.confirmed_at, p.index + 3)
            # Le pivot n'est pas connu avant sa confirmation.
            self.assertNotIn(p, pivots_known_at(pivots, p.confirmed_at - 1))
            self.assertIn(p, pivots_known_at(pivots, p.confirmed_at))

    def test_uptrend_structure(self):
        # Vagues montantes: HH/HL.
        closes = []
        base = 1.0
        for wave in range(6):
            for i in range(5):
                closes.append(base + i * 0.01)
            for i in range(3):
                closes.append(base + 0.05 - i * 0.008)
            base += 0.02
        candles = make_candles(closes, spread=0.0)
        pivots = find_pivots(candles, lookback=2)
        self.assertEqual(classify_structure(pivots), "up")


class TestSlope(unittest.TestCase):
    def test_positive(self):
        self.assertGreater(slope([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], 5), 0)

    def test_none_handling(self):
        self.assertIsNone(slope([None, None, 1.0], 5))


if __name__ == "__main__":
    unittest.main()
