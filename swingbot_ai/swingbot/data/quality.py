"""Data Quality Engine — fraîcheur, trous, doublons, bougies incomplètes.

Abstention par défaut (principe 10) : toute anomalie bloque la décision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .models import Candle
from ..constants import Timeframe


@dataclass
class QualityReport:
    ok: bool
    issues: list[str] = field(default_factory=list)


def check_series(candles: list[Candle], timeframe: Timeframe,
                 now: datetime | None = None,
                 max_staleness_bars: float = 2.0,
                 min_bars: int = 220) -> QualityReport:
    """Valide une série de bougies avant toute décision.

    - assez d'historique pour les indicateurs (EMA 200 => 220 bougies min) ;
    - timestamps strictement croissants, pas de doublons ;
    - pas de trous supérieurs à un weekend (le forex ferme ~49h le weekend) ;
    - dernière bougie clôturée et pas obsolète ;
    - valeurs OHLC cohérentes (high >= low, etc.).
    """
    issues: list[str] = []
    if len(candles) < min_bars:
        issues.append(f"historique insuffisant: {len(candles)} < {min_bars} bougies")
        return QualityReport(False, issues)

    step = timeframe.seconds
    weekend_tolerance = 3 * 24 * 3600  # gap weekend + jours fériés
    prev = None
    for c in candles:
        if not c.complete:
            issues.append(f"bougie incomplète à {c.ts.isoformat()}")
        if c.high < c.low or not (c.low <= c.open <= c.high) or not (c.low <= c.close <= c.high):
            issues.append(f"OHLC incohérent à {c.ts.isoformat()}")
        if prev is not None:
            delta = (c.ts - prev.ts).total_seconds()
            if delta <= 0:
                issues.append(f"doublon/ordre invalide à {c.ts.isoformat()}")
            elif delta > step + weekend_tolerance:
                issues.append(f"trou de données avant {c.ts.isoformat()} ({delta/3600:.0f}h)")
        prev = c
        if len(issues) >= 5:
            issues.append("... (autres anomalies tronquées)")
            break

    if now is not None and candles:
        age = (now - candles[-1].ts).total_seconds()
        # La dernière bougie ouvre à ts et couvre `step` secondes.
        if age > step * (1 + max_staleness_bars):
            issues.append(
                f"données obsolètes: dernière bougie {candles[-1].ts.isoformat()}, "
                f"âge {age/3600:.1f}h"
            )

    return QualityReport(ok=not issues, issues=issues)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
