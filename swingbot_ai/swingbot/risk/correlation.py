"""Corrélations et clusters d'exposition (6.3).

- corrélation glissante sur rendements Daily ;
- exposition par devise : EUR/USD long + GBP/USD long = exposition USD commune ;
- stress test à corrélation 1.
"""

from __future__ import annotations

import math

from ..constants import Direction
from ..data.models import Position, MAJORS


def rolling_correlation(returns_a: list[float], returns_b: list[float],
                        window: int = 60) -> float | None:
    """Corrélation de Pearson sur les `window` derniers rendements communs."""
    n = min(len(returns_a), len(returns_b), window)
    if n < 20:
        return None
    a = returns_a[-n:]
    b = returns_b[-n:]
    ma = sum(a) / n
    mb = sum(b) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va <= 0 or vb <= 0:
        return None
    return cov / math.sqrt(va * vb)


def currency_exposure(positions: list[Position]) -> dict[str, float]:
    """Exposition nette en risque monétaire par devise.

    Long EURUSD = long EUR / short USD. On agrège le risque monétaire signé.
    """
    expo: dict[str, float] = {}
    for p in positions:
        inst = MAJORS.get(p.symbol)
        if inst is None:
            continue
        sign = 1.0 if p.direction == Direction.LONG else -1.0
        expo[inst.base] = expo.get(inst.base, 0.0) + sign * p.risk_money
        expo[inst.quote] = expo.get(inst.quote, 0.0) - sign * p.risk_money
    return expo


def cluster_risk(positions: list[Position],
                 candidate: Position | None = None) -> dict[str, float]:
    """Risque agrégé par devise (valeur absolue), candidat inclus.

    Approche prudente : plusieurs positions exposées à la même devise
    comptent comme UNE exposition (corrélation 1 en stress)."""
    pos = list(positions)
    if candidate is not None:
        pos.append(candidate)
    expo = currency_exposure(pos)
    return {ccy: abs(v) for ccy, v in expo.items()}


def worst_cluster(positions: list[Position],
                  candidate: Position | None = None) -> tuple[str, float]:
    clusters = cluster_risk(positions, candidate)
    if not clusters:
        return ("", 0.0)
    ccy = max(clusters, key=lambda k: clusters[k])
    return (ccy, clusters[ccy])
