#!/usr/bin/env python3
"""Génère des CSV H4 synthétiques dans data/ pour tester la tuyauterie.

⚠ Données SYNTHÉTIQUES : elles valident le pipeline (backtest, shadow,
dashboard), jamais la stratégie. Remplacer par des données réelles
(8-12 ans, plusieurs régimes — section 11) avant toute conclusion.

Usage : python scripts/generate_sample_data.py [--bars 8000]
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from swingbot.data.provider import generate_synthetic_h4, save_csv

START_PRICES = {"EURUSD": 1.1000, "GBPUSD": 1.2700, "USDJPY": 148.00,
                "AUDUSD": 0.6600, "USDCAD": 1.3600}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", type=int, default=8000)
    args = ap.parse_args()

    data_dir = ROOT / "data"
    start = datetime(2018, 1, 1, tzinfo=timezone.utc)
    for i, (symbol, price) in enumerate(START_PRICES.items()):
        candles = generate_synthetic_h4(symbol, start, args.bars,
                                        seed=100 + i, start_price=price)
        path = data_dir / f"{symbol}_H4.csv"
        save_csv(path, candles)
        print(f"✓ {path} — {len(candles)} bougies "
              f"({candles[0].ts.date()} → {candles[-1].ts.date()})")
    print("\n⚠ Rappel : données synthétiques = test de tuyauterie uniquement.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
