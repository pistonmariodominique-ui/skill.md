"""Kill-switch (section 14) : arrêt immédiat des nouvelles entrées.

Le kill-switch est TOUJOURS prioritaire : quand il est armé, aucun signal
ne peut devenir un ordre, quel que soit le score. Il ne peut être désarmé
que manuellement (CLI) après revue humaine.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class KillSwitchEvent:
    ts: str
    reason: str
    detail: str = ""


@dataclass
class KillSwitch:
    """État persisté sur disque : survit à un redémarrage (section 16)."""
    state_path: Path
    armed: bool = False
    events: list[KillSwitchEvent] = field(default_factory=list)

    @staticmethod
    def load(state_path: Path) -> "KillSwitch":
        ks = KillSwitch(state_path=state_path)
        if state_path.exists():
            raw = json.loads(state_path.read_text(encoding="utf-8"))
            ks.armed = bool(raw.get("armed", False))
            ks.events = [KillSwitchEvent(**e) for e in raw.get("events", [])]
        return ks

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps({
            "armed": self.armed,
            "events": [e.__dict__ for e in self.events[-100:]],
        }, indent=2), encoding="utf-8")

    def trip(self, reason: str, detail: str = "") -> None:
        self.armed = True
        self.events.append(KillSwitchEvent(
            ts=datetime.now(timezone.utc).isoformat(), reason=reason, detail=detail))
        self._save()

    def reset_manual(self, operator: str) -> None:
        """Désarmement MANUEL uniquement, tracé au journal."""
        self.armed = False
        self.events.append(KillSwitchEvent(
            ts=datetime.now(timezone.utc).isoformat(),
            reason="manual_reset", detail=f"par {operator}"))
        self._save()


def evaluate_triggers(equity: float, peak_equity: float,
                      daily_pnl_pct: float, weekly_pnl_pct: float,
                      limits, data_ok: bool = True,
                      reconciliation_ok: bool = True,
                      broker_ok: bool = True,
                      sl_confirmed_everywhere: bool = True) -> list[str]:
    """Retourne la liste des déclencheurs actifs (vide = tout va bien)."""
    triggers: list[str] = []
    if peak_equity > 0:
        dd = (peak_equity - equity) / peak_equity * 100.0
        if dd >= limits.killswitch_drawdown_pct:
            triggers.append(f"drawdown {dd:.2f}% >= plafond {limits.killswitch_drawdown_pct}%")
    if daily_pnl_pct <= -limits.max_daily_loss_pct:
        triggers.append(f"perte journalière {daily_pnl_pct:.2f}% <= -{limits.max_daily_loss_pct}%")
    if weekly_pnl_pct <= -limits.max_weekly_loss_pct:
        triggers.append(f"perte hebdomadaire {weekly_pnl_pct:.2f}% <= -{limits.max_weekly_loss_pct}%")
    if not data_ok:
        triggers.append("données invalides ou obsolètes")
    if not reconciliation_ok:
        triggers.append("écart de réconciliation broker")
    if not broker_ok:
        triggers.append("broker indisponible")
    if not sl_confirmed_everywhere:
        triggers.append("stop-loss absent ou non confirmé sur une position")
    return triggers
