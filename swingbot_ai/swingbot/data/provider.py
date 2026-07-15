"""Fournisseurs de données : CSV local + générateur synthétique.

Le CSV est le format d'échange pour les données historiques réelles
(colonnes: timestamp,open,high,low,close,volume — timestamp ISO-8601 UTC).

Le générateur synthétique sert UNIQUEMENT à valider la tuyauterie
(backtest, dashboard, tests). Il ne prouve rien sur la rentabilité :
utiliser des données réelles avant toute conclusion (section 11).
"""

from __future__ import annotations

import csv
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import Candle
from ..constants import Timeframe


def load_csv(path: Path, timeframe: Timeframe) -> list[Candle]:
    candles: list[Candle] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ts = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            candles.append(Candle(
                ts=ts,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("volume") or 0.0),
                timeframe=timeframe,
            ))
    candles.sort(key=lambda c: c.ts)
    return candles


def save_csv(path: Path, candles: list[Candle]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for c in candles:
            w.writerow([c.ts.isoformat(), f"{c.open:.5f}", f"{c.high:.5f}",
                        f"{c.low:.5f}", f"{c.close:.5f}", f"{c.volume:.0f}"])


def _is_weekend(ts: datetime) -> bool:
    # Forex fermé du vendredi 21h UTC au dimanche 21h UTC (approximation).
    wd, h = ts.weekday(), ts.hour
    return (wd == 4 and h >= 21) or wd == 5 or (wd == 6 and h < 21)


def generate_synthetic_h4(symbol: str, start: datetime, bars: int,
                          seed: int | None = None,
                          start_price: float = 1.1000) -> list[Candle]:
    """Série H4 synthétique avec régimes alternés (tendance/range) et
    volatilité variable, pour tester le pipeline de bout en bout."""
    rng = random.Random(seed if seed is not None else hash(symbol) & 0xFFFF)
    candles: list[Candle] = []
    price = start_price
    ts = start.replace(minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    ts = ts.replace(hour=(ts.hour // 4) * 4)

    drift = 0.0
    vol = 0.0016
    regime_left = 0

    while len(candles) < bars:
        if _is_weekend(ts):
            ts += timedelta(hours=4)
            continue
        if regime_left <= 0:
            # Nouveau régime : tendance haussière, baissière ou range.
            r = rng.random()
            if r < 0.35:
                drift = rng.uniform(0.00025, 0.0009)
            elif r < 0.70:
                drift = -rng.uniform(0.00025, 0.0009)
            else:
                drift = rng.uniform(-0.00008, 0.00008)
            vol = rng.uniform(0.0009, 0.0026)
            regime_left = rng.randint(60, 240)
        regime_left -= 1

        o = price
        ret = rng.gauss(drift, vol)
        c = max(0.01, o * (1 + ret))
        wick = abs(rng.gauss(0, vol * 0.7)) * o
        h = max(o, c) + wick
        l = min(o, c) - abs(rng.gauss(0, vol * 0.7)) * o
        candles.append(Candle(ts=ts, open=round(o, 5), high=round(h, 5),
                              low=round(max(0.01, l), 5), close=round(c, 5),
                              volume=float(rng.randint(500, 5000)),
                              timeframe=Timeframe.H4))
        price = c
        ts += timedelta(hours=4)
    return candles


def resample(candles: list[Candle], target: Timeframe) -> list[Candle]:
    """Agrège des bougies H4 en Daily ou Weekly (UTC, semaine lundi 00:00).

    Seules les périodes CLÔTURÉES sont retournées si la dernière période
    est incomplète on la garde marquée complete=False (jamais utilisée
    pour décider — principe 5.2.6).
    """
    if not candles:
        return []

    def bucket(ts: datetime) -> datetime:
        if target == Timeframe.D1:
            return ts.replace(hour=0, minute=0, second=0, microsecond=0)
        if target == Timeframe.W1:
            d = ts.replace(hour=0, minute=0, second=0, microsecond=0)
            return d - timedelta(days=d.weekday())
        raise ValueError(f"resample vers {target} non supporté")

    out: list[Candle] = []
    cur_key = None
    o = h = l = c = v = 0.0
    for cd in candles:
        k = bucket(cd.ts)
        if k != cur_key:
            if cur_key is not None:
                out.append(Candle(ts=cur_key, open=o, high=h, low=l, close=c,
                                  volume=v, timeframe=target, complete=True))
            cur_key, o, h, l, c, v = k, cd.open, cd.high, cd.low, cd.close, cd.volume
        else:
            h = max(h, cd.high)
            l = min(l, cd.low)
            c = cd.close
            v += cd.volume
    if cur_key is not None:
        # Dernière période : potentiellement incomplète.
        out.append(Candle(ts=cur_key, open=o, high=h, low=l, close=c,
                          volume=v, timeframe=target, complete=False))
    return out
