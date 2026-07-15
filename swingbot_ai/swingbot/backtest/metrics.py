"""Métriques de performance (section 11) et portes de passage en shadow."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .engine import BtResult, BtTrade


@dataclass
class Gates:
    """Critères minimaux candidats au passage en shadow (section 11).

    Ces seuils ne prouvent pas une rentabilité future ; ils évitent
    seulement les candidats manifestement fragiles."""
    min_profit_factor: float = 1.20
    min_expectancy_r: float = 0.10
    min_trades: int = 150
    max_drawdown_pct: float = 8.0


def compute_metrics(result: BtResult) -> dict:
    trades = result.trades
    n = len(trades)
    m: dict = {"n_trades": n}
    if n == 0:
        m.update({"profit_factor": 0.0, "expectancy_r": 0.0, "win_rate": 0.0,
                  "max_drawdown_pct": 0.0, "net_return_pct": 0.0,
                  "sharpe": 0.0, "sortino": 0.0, "total_swap": 0.0,
                  "total_costs": 0.0, "avg_bars_held": 0.0})
        return m

    wins = [t.pnl_money for t in trades if t.pnl_money > 0]
    losses = [-t.pnl_money for t in trades if t.pnl_money < 0]
    gross_win = sum(wins)
    gross_loss = sum(losses)
    m["profit_factor"] = round(gross_win / gross_loss, 3) if gross_loss > 0 else float("inf")
    m["expectancy_r"] = round(sum(t.pnl_r for t in trades) / n, 3)
    m["win_rate"] = round(len(wins) / n * 100, 1)
    m["avg_win"] = round(gross_win / len(wins), 2) if wins else 0.0
    m["avg_loss"] = round(gross_loss / len(losses), 2) if losses else 0.0
    m["total_swap"] = round(sum(t.swap_money for t in trades), 2)
    m["total_costs"] = round(sum(t.costs_money for t in trades), 2)
    m["avg_bars_held"] = round(sum(t.bars_held for t in trades) / n, 1)

    # Drawdown sur la courbe d'equity.
    peak = result.initial_equity
    max_dd = 0.0
    dd_start = None
    max_dd_bars = 0
    cur_dd_bars = 0
    for _, eq in result.equity_curve:
        if eq > peak:
            peak = eq
            cur_dd_bars = 0
        else:
            cur_dd_bars += 1
            max_dd_bars = max(max_dd_bars, cur_dd_bars)
        if peak > 0:
            max_dd = max(max_dd, (peak - eq) / peak * 100)
    m["max_drawdown_pct"] = round(max_dd, 2)
    m["max_drawdown_bars"] = max_dd_bars
    m["net_return_pct"] = round(
        (result.final_equity - result.initial_equity) / result.initial_equity * 100, 2)

    # Sharpe/Sortino approximés sur les rendements par trade.
    rets = [t.pnl_money / result.initial_equity for t in trades]
    mean = sum(rets) / n
    var = sum((r - mean) ** 2 for r in rets) / n if n > 1 else 0.0
    std = math.sqrt(var)
    downside = [r for r in rets if r < 0]
    dvar = sum(r ** 2 for r in downside) / n if downside else 0.0
    dstd = math.sqrt(dvar)
    scale = math.sqrt(50)  # ~50 trades/an hypothétique pour l'annualisation
    m["sharpe"] = round(mean / std * scale, 2) if std > 0 else 0.0
    m["sortino"] = round(mean / dstd * scale, 2) if dstd > 0 else 0.0

    # Répartitions utiles.
    m["by_exit_reason"] = {}
    for t in trades:
        m["by_exit_reason"].setdefault(t.exit_reason, 0)
        m["by_exit_reason"][t.exit_reason] += 1
    m["by_direction"] = {
        "long": round(sum(t.pnl_money for t in trades if t.direction == "long"), 2),
        "short": round(sum(t.pnl_money for t in trades if t.direction == "short"), 2),
    }
    return m


def check_gates(metrics: dict, gates: Gates,
                stressed_metrics: dict | None = None,
                mc_p95_drawdown: float | None = None) -> tuple[bool, list[str]]:
    """Vérifie les portes de passage en shadow. Un seul échec = NO-GO."""
    fails: list[str] = []
    if metrics.get("profit_factor", 0) < gates.min_profit_factor:
        fails.append(f"profit factor {metrics.get('profit_factor')} < {gates.min_profit_factor}")
    if metrics.get("expectancy_r", 0) < gates.min_expectancy_r:
        fails.append(f"expectancy {metrics.get('expectancy_r')}R < {gates.min_expectancy_r}R")
    if metrics.get("n_trades", 0) < gates.min_trades:
        fails.append(f"{metrics.get('n_trades')} trades < {gates.min_trades}")
    if metrics.get("max_drawdown_pct", 100) > gates.max_drawdown_pct:
        fails.append(f"drawdown {metrics.get('max_drawdown_pct')}% > {gates.max_drawdown_pct}%")
    if stressed_metrics is not None and stressed_metrics.get("net_return_pct", -1) <= 0:
        fails.append("résultat négatif avec coûts x1.5")
    if mc_p95_drawdown is not None and mc_p95_drawdown > gates.max_drawdown_pct:
        fails.append(f"Monte-Carlo p95 drawdown {mc_p95_drawdown:.1f}% > {gates.max_drawdown_pct}%")
    return (not fails, fails)
