"""Walk-forward : découpe la série en plis train/test successifs (section 11).

V1 : les paramètres sont FIGÉS (pas d'optimisation automatique) — le
walk-forward vérifie la stabilité des résultats hors échantillon sur des
fenêtres glissantes. L'optimisation sur train, si un jour elle est ajoutée,
ne devra JAMAIS toucher les fenêtres de test.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..data.models import Candle
from ..strategy.swing_pullback import StrategyParams
from .costs import CostModel
from .engine import run_backtest
from .metrics import compute_metrics


@dataclass
class WalkForwardFold:
    fold: int
    test_start: str
    test_end: str
    metrics: dict


def run_walk_forward(symbol: str, h4: list[Candle], params: StrategyParams,
                     costs: CostModel, initial_equity: float = 10_000.0,
                     train_bars: int = 1500, test_bars: int = 375,
                     warmup: int = 260) -> list[WalkForwardFold]:
    folds: list[WalkForwardFold] = []
    fold_num = 0
    start = 0
    while start + train_bars + test_bars <= len(h4):
        # La fenêtre de test dispose du train précédent comme contexte
        # (warmup), mais les métriques ne comptent que les trades du test.
        segment = h4[start: start + train_bars + test_bars]
        res = run_backtest(symbol, segment, params, costs, initial_equity,
                           warmup=train_bars)
        test_range = (segment[train_bars].ts.isoformat(),
                      segment[-1].ts.isoformat())
        folds.append(WalkForwardFold(
            fold=fold_num, test_start=test_range[0], test_end=test_range[1],
            metrics=compute_metrics(res)))
        fold_num += 1
        start += test_bars
    return folds


def degradation_check(folds: list[WalkForwardFold],
                      min_positive_ratio: float = 0.5) -> tuple[bool, str]:
    """Pas de dégradation majeure : au moins la moitié des plis avec
    expectancy positive, et pas de pli catastrophique (< -0.5R)."""
    if not folds:
        return False, "aucun pli walk-forward"
    with_trades = [f for f in folds if f.metrics.get("n_trades", 0) > 0]
    if not with_trades:
        return False, "aucun trade sur l'ensemble des plis"
    positive = sum(1 for f in with_trades if f.metrics.get("expectancy_r", 0) > 0)
    ratio = positive / len(with_trades)
    worst = min(f.metrics.get("expectancy_r", 0) for f in with_trades)
    if ratio < min_positive_ratio:
        return False, f"seulement {positive}/{len(with_trades)} plis positifs"
    if worst < -0.5:
        return False, f"pli catastrophique à {worst}R"
    return True, f"{positive}/{len(with_trades)} plis positifs, pire pli {worst}R"
