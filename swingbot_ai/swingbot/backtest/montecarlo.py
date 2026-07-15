"""Monte-Carlo sur l'ordre des trades (section 11).

Rebats l'ordre des P&L de trades pour estimer la distribution du drawdown :
si le 95e percentile dépasse le plafond toléré, le candidat est fragile.
"""

from __future__ import annotations

import random


def montecarlo_drawdown(pnls: list[float], initial_equity: float,
                        runs: int = 1000, seed: int = 42) -> dict:
    if not pnls:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "worst": 0.0}
    rng = random.Random(seed)
    drawdowns: list[float] = []
    for _ in range(runs):
        order = pnls[:]
        rng.shuffle(order)
        eq = initial_equity
        peak = eq
        max_dd = 0.0
        for p in order:
            eq += p
            peak = max(peak, eq)
            if peak > 0:
                max_dd = max(max_dd, (peak - eq) / peak * 100)
        drawdowns.append(max_dd)
    drawdowns.sort()

    def pct(p: float) -> float:
        idx = min(len(drawdowns) - 1, int(p * len(drawdowns)))
        return round(drawdowns[idx], 2)

    return {"p50": pct(0.50), "p95": pct(0.95), "p99": pct(0.99),
            "worst": round(drawdowns[-1], 2), "runs": runs}
