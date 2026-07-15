"""Stratégie de référence V1 : swing pullback multi-timeframes (section 5).

Hypothèse à INVALIDER ou confirmer — pas supposée rentable.

Setup (5.2) :
1. Tendance Weekly/Daily alignée ou Weekly non opposée.
2. Pullback H4 vers zone déterministe : EMA20/50 H4.
3. Confirmation H4 à la clôture : rejet, engulfing ou cassure du dernier pivot.
4. Distance au prochain obstacle >= min_rr net de coûts.
5. Entrée uniquement sur bougie clôturée.

Stop (5.3) : au-delà du pivot structurel + buffer ATR Daily.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from ..constants import Direction, Regime
from ..data.models import Candle, Instrument, Signal
from ..features.engine import FeatureSet
from ..features.structure import last_pivot
from .regime import detect_regime, weekly_not_opposed


@dataclass
class StrategyParams:
    ema_fast: int = 20
    ema_mid: int = 50
    ema_slow: int = 200
    atr_period: int = 14
    adx_min: float = 0.0
    pivot_lookback: int = 5
    sl_buffer_atr_daily: float = 0.2
    min_rr_net: float = 2.0
    signal_ttl_h4_bars: int = 2
    version: str = "1.0.0"

    @staticmethod
    def from_config(cfg: dict) -> "StrategyParams":
        return StrategyParams(
            ema_fast=int(cfg.get("ema_fast", 20)),
            ema_mid=int(cfg.get("ema_mid", 50)),
            ema_slow=int(cfg.get("ema_slow", 200)),
            atr_period=int(cfg.get("atr_period", 14)),
            adx_min=float(cfg.get("adx_min", 0)),
            pivot_lookback=int(cfg.get("pivot_lookback", 5)),
            sl_buffer_atr_daily=float(cfg.get("sl_buffer_atr_daily", 0.2)),
            min_rr_net=float(cfg.get("min_rr_net", 2.0)),
            signal_ttl_h4_bars=int(cfg.get("signal_ttl_h4_bars", 2)),
            version=str(cfg.get("version", "1.0.0")),
        )


def _is_bullish_confirmation(prev: Candle, cur: Candle) -> str | None:
    """Rejet (pin bar), engulfing haussier ou cassure du high précédent."""
    body = abs(cur.close - cur.open)
    rng = cur.high - cur.low
    lower_wick = min(cur.open, cur.close) - cur.low
    if rng > 0 and lower_wick > rng * 0.5 and cur.close > cur.open:
        return "rejet (pin bar haussier)"
    if cur.close > cur.open and prev.close < prev.open and \
       cur.close > prev.open and cur.open <= prev.close and body > 0:
        return "engulfing haussier"
    if cur.close > prev.high:
        return "cassure du high précédent"
    return None


def _is_bearish_confirmation(prev: Candle, cur: Candle) -> str | None:
    body = abs(cur.close - cur.open)
    rng = cur.high - cur.low
    upper_wick = cur.high - max(cur.open, cur.close)
    if rng > 0 and upper_wick > rng * 0.5 and cur.close < cur.open:
        return "rejet (pin bar baissier)"
    if cur.close < cur.open and prev.close > prev.open and \
       cur.close < prev.open and cur.open >= prev.close and body > 0:
        return "engulfing baissier"
    if cur.close < prev.low:
        return "cassure du low précédent"
    return None


def evaluate(symbol: str, instrument: Instrument, fs: FeatureSet,
             params: StrategyParams,
             est_cost_price_units: float = 0.0) -> Signal | None:
    """Évalue le setup à la clôture de la dernière bougie H4.

    Retourne None si aucun candidat, ou un Signal (éventuellement avec
    abstain_reasons remplies si un critère bloque — pour le journal).
    `est_cost_price_units` : coût aller-retour estimé (spread+slippage)
    exprimé en unités de prix, pour exiger un R:R NET (5.2.4).
    """
    if len(fs.h4) < 210 or not fs.daily:
        return None
    cur = fs.h4[-1]
    prev = fs.h4[-2]
    reasons: list[str] = []
    abstain: list[str] = []

    regime, regime_reasons = detect_regime(fs, adx_min=params.adx_min)
    if regime not in (Regime.BULLISH, Regime.BEARISH):
        return None  # pas de candidat en range/incertain — inactivité assumée
    reasons += regime_reasons

    bullish = regime == Regime.BULLISH
    direction = Direction.LONG if bullish else Direction.SHORT

    if not weekly_not_opposed(fs, bullish):
        return None  # Weekly opposée : pas de candidat
    reasons.append("Weekly alignée ou non opposée")

    # 2. Pullback H4 vers EMA20/50 : la bougie doit avoir touché la zone.
    ema20 = fs.ema20_h4[-1]
    ema50 = fs.ema50_h4[-1]
    if ema20 is None or ema50 is None:
        return None
    zone_hi = max(ema20, ema50)
    zone_lo = min(ema20, ema50)
    atr_h4 = fs.atr_h4[-1] or 0.0
    tolerance = atr_h4 * 0.25
    if bullish:
        touched = cur.low <= zone_hi + tolerance and cur.close >= zone_lo - tolerance
    else:
        touched = cur.high >= zone_lo - tolerance and cur.close <= zone_hi + tolerance
    if not touched:
        return None
    reasons.append(f"pullback H4 dans la zone EMA{params.ema_fast}/{params.ema_mid}")

    # 3. Confirmation à la clôture H4.
    conf = _is_bullish_confirmation(prev, cur) if bullish else _is_bearish_confirmation(prev, cur)
    if conf is None:
        return None
    reasons.append(f"confirmation H4 : {conf}")

    # 5.3 Stop : au-delà du pivot structurel H4 + buffer ATR Daily.
    pivots = fs.h4_pivots_known()
    pivot = last_pivot(pivots, "low" if bullish else "high")
    atr_d = fs.atr_d[-1]
    if pivot is None or atr_d is None:
        return None
    buffer = params.sl_buffer_atr_daily * atr_d
    entry = cur.close
    if bullish:
        stop = pivot.price - buffer
        if stop >= entry:
            return None
        stop_dist = entry - stop
    else:
        stop = pivot.price + buffer
        if stop <= entry:
            return None
        stop_dist = stop - entry

    # Garde-fou : stop absurde (trop serré ou trop large vs ATR Daily).
    if stop_dist < 0.3 * atr_d:
        abstain.append(f"stop trop serré ({stop_dist:.5f} < 0.3 ATR D)")
    if stop_dist > 3.0 * atr_d:
        abstain.append(f"stop trop large ({stop_dist:.5f} > 3 ATR D)")

    # 4. Obstacle : prochain pivot Daily opposé — il faut >= min_rr NET.
    d_pivots = fs.pivots_d
    known_d = [p for p in d_pivots if p.confirmed_at <= len(fs.daily) - 1]
    if bullish:
        obstacles = [p.price for p in known_d if p.kind == "high" and p.price > entry]
        obstacle = min(obstacles) if obstacles else entry + 4 * stop_dist
        room = obstacle - entry
    else:
        obstacles = [p.price for p in known_d if p.kind == "low" and p.price < entry]
        obstacle = max(obstacles) if obstacles else entry - 4 * stop_dist
        room = entry - obstacle

    net_room = room - est_cost_price_units
    rr = net_room / stop_dist if stop_dist > 0 else 0.0
    if rr < params.min_rr_net:
        abstain.append(f"R:R net {rr:.2f} < minimum {params.min_rr_net}")
    else:
        reasons.append(f"R:R net estimé {rr:.2f} (obstacle {obstacle:.5f})")

    # Target par défaut : 2R net (le trailing gère le reste).
    if bullish:
        target = entry + max(params.min_rr_net * stop_dist, min(net_room, 4 * stop_dist))
    else:
        target = entry - max(params.min_rr_net * stop_dist, min(net_room, 4 * stop_dist))

    return Signal(
        signal_id=str(uuid.uuid4()),
        ts=cur.ts,
        symbol=symbol,
        direction=direction,
        entry_price=entry,
        stop_price=round(stop, 5),
        target_price=round(target, 5),
        rr_expected=round(rr, 2),
        regime=regime.value,
        score=min(1.0, rr / 4.0) if not abstain else 0.0,
        reasons=reasons,
        abstain_reasons=abstain,
        strategy_version=params.version,
        expires_after_bars=params.signal_ttl_h4_bars,
    )
