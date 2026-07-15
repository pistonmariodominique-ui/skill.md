"""Risk Engine : validation finale d'un candidat avant exécution (section 6).

Toutes les vérifications retournent des motifs explicites — chaque refus
est journalisé (décisions explicables et auditables, section 1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time

from ..config import RiskLimits
from ..constants import Direction
from ..data.models import Position, Signal
from .correlation import worst_cluster


@dataclass
class RiskDecision:
    approved: bool
    reasons: list[str] = field(default_factory=list)


def open_risk_money(positions: list[Position]) -> float:
    return sum(p.risk_money for p in positions)


def check_candidate(signal: Signal, candidate_pos: Position,
                    open_positions: list[Position], equity: float,
                    limits: RiskLimits, killswitch_armed: bool,
                    daily_pnl_pct: float, weekly_pnl_pct: float,
                    now_utc: datetime,
                    friday_cutoff: str = "15:00") -> RiskDecision:
    """Chaîne complète de contrôles pré-trade. TOUT doit passer."""
    reasons: list[str] = []

    if killswitch_armed:
        return RiskDecision(False, ["kill-switch armé — aucune nouvelle entrée"])

    # Weekend (6.4) : pas de nouvelle entrée le vendredi après l'heure limite.
    if now_utc.weekday() == 4:
        hh, mm = (int(x) for x in friday_cutoff.split(":"))
        if now_utc.time() >= time(hh, mm):
            reasons.append(f"vendredi après {friday_cutoff} UTC — pas de nouvelle entrée")
    if now_utc.weekday() in (5, 6):
        reasons.append("weekend — marché fermé")

    # Pertes journalière/hebdomadaire déjà au plafond.
    if daily_pnl_pct <= -limits.max_daily_loss_pct:
        reasons.append(f"perte journalière {daily_pnl_pct:.2f}% au plafond")
    if weekly_pnl_pct <= -limits.max_weekly_loss_pct:
        reasons.append(f"perte hebdomadaire {weekly_pnl_pct:.2f}% au plafond")

    # Nombre de positions.
    if len(open_positions) >= limits.max_positions:
        reasons.append(f"{len(open_positions)} positions ouvertes >= max {limits.max_positions}")

    # Doublon : jamais deux positions sur le même symbole.
    if any(p.symbol == signal.symbol for p in open_positions):
        reasons.append(f"position déjà ouverte sur {signal.symbol}")

    # Risque du trade lui-même.
    per_trade_cap = equity * limits.risk_per_trade_pct / 100.0
    if candidate_pos.risk_money > per_trade_cap * 1.001:  # tolérance d'arrondi
        reasons.append(
            f"risque trade {candidate_pos.risk_money:.2f} > plafond {per_trade_cap:.2f}")

    # Risque ouvert total.
    total = open_risk_money(open_positions) + candidate_pos.risk_money
    total_cap = equity * limits.max_open_risk_pct / 100.0
    if total > total_cap * 1.001:
        reasons.append(f"risque ouvert total {total:.2f} > plafond {total_cap:.2f}")

    # Cluster corrélé (6.3) : agrégation par devise, corrélation 1 en stress.
    ccy, cluster = worst_cluster(open_positions, candidate_pos)
    cluster_cap = equity * limits.max_cluster_risk_pct / 100.0
    if cluster > cluster_cap * 1.001:
        reasons.append(
            f"cluster {ccy} à {cluster:.2f} > plafond corrélé {cluster_cap:.2f}")

    if reasons:
        return RiskDecision(False, reasons)
    return RiskDecision(True, [
        f"risque trade {candidate_pos.risk_money:.2f} <= {per_trade_cap:.2f}",
        f"risque ouvert {total:.2f} <= {total_cap:.2f}",
        f"pire cluster {ccy} {cluster:.2f} <= {cluster_cap:.2f}",
    ])
