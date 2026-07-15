"""Structure de marché : pivots fractals, HH/HL vs LH/LL.

Un pivot haut à l'indice i exige `lookback` bougies de chaque côté avec des
highs inférieurs — donc un pivot n'est CONNU que `lookback` bougies plus
tard. C'est essentiel pour éviter la fuite du futur (principe 6).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..data.models import Candle


@dataclass(frozen=True)
class Pivot:
    index: int          # indice de la bougie pivot
    confirmed_at: int   # indice où le pivot devient connu (index + lookback)
    price: float
    kind: str           # "high" | "low"


def find_pivots(candles: list[Candle], lookback: int = 5) -> list[Pivot]:
    pivots: list[Pivot] = []
    n = len(candles)
    for i in range(lookback, n - lookback):
        h = candles[i].high
        l = candles[i].low
        # Strict à gauche, non-strict à droite : en cas d'égalité de highs
        # (plateau), la PREMIÈRE bougie du plateau est le pivot.
        if all(candles[j].high < h for j in range(i - lookback, i)) and \
           all(candles[j].high <= h for j in range(i + 1, i + lookback + 1)):
            pivots.append(Pivot(i, i + lookback, h, "high"))
        if all(candles[j].low > l for j in range(i - lookback, i)) and \
           all(candles[j].low >= l for j in range(i + 1, i + lookback + 1)):
            pivots.append(Pivot(i, i + lookback, l, "low"))
    pivots.sort(key=lambda p: p.index)
    return pivots


def pivots_known_at(pivots: list[Pivot], bar_index: int) -> list[Pivot]:
    """Seuls les pivots confirmés à `bar_index` sont utilisables pour décider."""
    return [p for p in pivots if p.confirmed_at <= bar_index]


def classify_structure(pivots: list[Pivot]) -> str:
    """HH/HL => "up", LH/LL => "down", sinon "mixed".

    Compare les deux derniers pivots hauts et les deux derniers pivots bas.
    """
    highs = [p for p in pivots if p.kind == "high"][-2:]
    lows = [p for p in pivots if p.kind == "low"][-2:]
    if len(highs) < 2 or len(lows) < 2:
        return "mixed"
    hh = highs[1].price > highs[0].price
    hl = lows[1].price > lows[0].price
    lh = highs[1].price < highs[0].price
    ll = lows[1].price < lows[0].price
    if hh and hl:
        return "up"
    if lh and ll:
        return "down"
    return "mixed"


def last_pivot(pivots: list[Pivot], kind: str) -> Pivot | None:
    for p in reversed(pivots):
        if p.kind == kind:
            return p
    return None
