"""Backtester événementiel H4, sans fuite du futur (section 11).

Règles anti-lookahead :
- décision à la CLÔTURE de la bougie i, entrée à l'OUVERTURE de i+1
  (jamais d'utilisation de la bougie complète pour entrer à son ouverture) ;
- pivots utilisés seulement une fois confirmés (lookback bougies plus tard) ;
- intra-bougie pessimiste : si SL et TP touchés dans la même bougie H4,
  le SL est réputé touché en premier ;
- gap au-delà du stop : exécution au premier prix disponible (l'open).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..constants import Direction
from ..data.models import Candle, Instrument, MAJORS
from ..features.engine import compute_features
from ..features.structure import find_pivots, pivots_known_at, last_pivot
from ..strategy.swing_pullback import StrategyParams, evaluate
from .costs import CostModel


@dataclass
class BtTrade:
    symbol: str
    direction: str
    entry_ts: str
    exit_ts: str
    entry_price: float
    exit_price: float
    stop_price: float
    units: float
    pnl_money: float
    pnl_r: float
    swap_money: float
    costs_money: float
    exit_reason: str
    bars_held: int


@dataclass
class BtResult:
    trades: list[BtTrade] = field(default_factory=list)
    equity_curve: list[tuple[str, float]] = field(default_factory=list)
    initial_equity: float = 10_000.0
    final_equity: float = 10_000.0


@dataclass
class _OpenPos:
    direction: Direction
    entry_price: float
    stop: float
    target: float | None
    units: float
    risk_money: float
    entry_index: int
    entry_ts: datetime
    swap_money: float = 0.0
    costs_money: float = 0.0
    breakeven_moved: bool = False
    last_swap_date: str = ""


def run_backtest(symbol: str, h4: list[Candle], params: StrategyParams,
                 costs: CostModel, initial_equity: float = 10_000.0,
                 risk_pct: float = 0.5,
                 breakeven_after_r: float = 1.0,
                 time_stop_bars: int = 30,
                 warmup: int = 260) -> BtResult:
    """Backtest mono-instrument (l'agrégation portfolio se fait au-dessus)."""
    inst: Instrument = MAJORS[symbol]
    pip = inst.pip_size
    equity = initial_equity
    result = BtResult(initial_equity=initial_equity)
    pos: _OpenPos | None = None
    pending = None  # signal pris à la clôture de i, exécuté à l'open de i+1

    all_pivots = find_pivots(h4, params.pivot_lookback)

    for i in range(warmup, len(h4)):
        bar = h4[i]

        # ---- 1. Exécuter l'entrée en attente à l'OPEN de cette bougie ----
        if pending is not None and pos is None:
            sig = pending
            pending = None
            spread = costs.spread_pips() * pip
            slip = costs.slippage_pips() * pip
            if sig.direction == Direction.LONG:
                fill = bar.open + spread / 2 + slip
            else:
                fill = bar.open - spread / 2 - slip
            stop_dist = abs(fill - sig.stop_price)
            min_dist = inst.min_stop_distance_pips * pip
            if stop_dist >= min_dist and stop_dist > 0:
                risk_money = equity * risk_pct / 100.0
                units = risk_money / stop_dist
                cost_money = spread / 2 * units + costs.commission_per_lot * units / inst.lot_size
                pos = _OpenPos(
                    direction=sig.direction, entry_price=fill,
                    stop=sig.stop_price, target=sig.target_price,
                    units=units, risk_money=risk_money, entry_index=i,
                    entry_ts=bar.ts, costs_money=cost_money,
                    last_swap_date=bar.ts.date().isoformat())

        # ---- 2. Gérer la position ouverte sur cette bougie ----
        if pos is not None:
            exit_price = None
            exit_reason = ""
            is_long = pos.direction == Direction.LONG

            # Swap journalier (chaque nouveau jour calendaire).
            d = bar.ts.date().isoformat()
            if d != pos.last_swap_date:
                swap_pips = costs.swap_pips_for_day(is_long, bar.ts.weekday())
                pos.swap_money += swap_pips * pip * pos.units
                pos.last_swap_date = d

            # Gap à l'ouverture au-delà du stop : premier prix disponible.
            if is_long and bar.open <= pos.stop:
                exit_price, exit_reason = bar.open, "gap_stop"
            elif not is_long and bar.open >= pos.stop:
                exit_price, exit_reason = bar.open, "gap_stop"
            # SL intra-bougie (prioritaire sur TP — pessimiste).
            elif is_long and bar.low <= pos.stop:
                exit_price, exit_reason = pos.stop, "stop"
            elif not is_long and bar.high >= pos.stop:
                exit_price, exit_reason = pos.stop, "stop"
            # TP.
            elif pos.target is not None and is_long and bar.high >= pos.target:
                exit_price, exit_reason = pos.target, "target"
            elif pos.target is not None and not is_long and bar.low <= pos.target:
                exit_price, exit_reason = pos.target, "target"
            # Sortie temporelle (5.3) : le setup n'évolue pas.
            elif i - pos.entry_index >= time_stop_bars:
                exit_price, exit_reason = bar.close, "time_stop"

            if exit_price is not None:
                slip = costs.slippage_pips() * pip if exit_reason in ("stop", "gap_stop") else 0.0
                if is_long:
                    exit_price -= slip
                else:
                    exit_price += slip
                sign = 1.0 if is_long else -1.0
                gross = sign * (exit_price - pos.entry_price) * pos.units
                pnl = gross + pos.swap_money - pos.costs_money
                stop_dist0 = abs(pos.entry_price - pos.stop) if not pos.breakeven_moved else None
                r_unit = pos.risk_money
                pnl_r = pnl / r_unit if r_unit > 0 else 0.0
                equity += pnl
                result.trades.append(BtTrade(
                    symbol=symbol, direction=pos.direction.value,
                    entry_ts=pos.entry_ts.isoformat(), exit_ts=bar.ts.isoformat(),
                    entry_price=round(pos.entry_price, 5),
                    exit_price=round(exit_price, 5),
                    stop_price=round(pos.stop, 5), units=round(pos.units, 2),
                    pnl_money=round(pnl, 2), pnl_r=round(pnl_r, 3),
                    swap_money=round(pos.swap_money, 2),
                    costs_money=round(pos.costs_money, 2),
                    exit_reason=exit_reason, bars_held=i - pos.entry_index))
                pos = None
            else:
                # Gestion : break-even après 1R (jamais avant — 5.3), puis
                # trailing sur pivot H4 confirmé.
                move = (bar.close - pos.entry_price) if is_long else (pos.entry_price - bar.close)
                r_now = move / abs(pos.entry_price - pos.stop) if abs(pos.entry_price - pos.stop) > 0 else 0
                if not pos.breakeven_moved and r_now >= breakeven_after_r:
                    pos.stop = pos.entry_price
                    pos.breakeven_moved = True
                elif pos.breakeven_moved:
                    known = pivots_known_at(all_pivots, i)
                    piv = last_pivot(known, "low" if is_long else "high")
                    if piv is not None:
                        if is_long and piv.price > pos.stop:
                            pos.stop = piv.price
                        elif not is_long and piv.price < pos.stop:
                            pos.stop = piv.price

        # ---- 3. Chercher un signal à la CLÔTURE de cette bougie ----
        if pos is None and pending is None and i >= warmup:
            # Fenêtre glissante bornée : 1800 bougies H4 suffisent pour
            # l'EMA200 Daily (200 jours = 1200 H4) + marge, et gardent le
            # backtest en O(n) plutôt qu'en O(n²).
            window = h4[max(0, i - 1799): i + 1]
            fs = compute_features(window, params.ema_fast, params.ema_mid,
                                  params.ema_slow, params.atr_period,
                                  14, params.pivot_lookback)
            est_cost = (costs.spread_pips() + costs.slippage_pips_max) * pip
            sig = evaluate(symbol, inst, fs, params, est_cost_price_units=est_cost)
            if sig is not None and sig.is_actionable:
                pending = sig

        result.equity_curve.append((bar.ts.isoformat(), round(equity, 2)))

    result.final_equity = equity
    return result
