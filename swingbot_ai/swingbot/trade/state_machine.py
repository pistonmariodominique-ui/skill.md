"""Machine d'états d'un trade (section 8).

Chaque transition porte : timestamp UTC, version de stratégie, décision,
motif, payload broker nettoyé et identifiant idempotent.
Toute transition non autorisée lève — un état incohérent doit faire du
bruit, jamais passer silencieusement.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..constants import ALLOWED_TRANSITIONS, TradeState


class IllegalTransition(Exception):
    pass


@dataclass
class Transition:
    ts: str
    from_state: str
    to_state: str
    reason: str
    strategy_version: str
    idempotency_key: str
    broker_payload: dict = field(default_factory=dict)


@dataclass
class TradeLifecycle:
    trade_id: str
    symbol: str
    strategy_version: str
    state: TradeState = TradeState.CANDIDATE
    transitions: list[Transition] = field(default_factory=list)

    @staticmethod
    def new(symbol: str, strategy_version: str) -> "TradeLifecycle":
        return TradeLifecycle(trade_id=str(uuid.uuid4()), symbol=symbol,
                              strategy_version=strategy_version)

    def transition(self, to_state: TradeState, reason: str,
                   broker_payload: dict | None = None) -> Transition:
        allowed = ALLOWED_TRANSITIONS.get(self.state, set())
        if to_state not in allowed:
            raise IllegalTransition(
                f"{self.trade_id}: {self.state.value} -> {to_state.value} interdit "
                f"(autorisés: {sorted(s.value for s in allowed)})")
        tr = Transition(
            ts=datetime.now(timezone.utc).isoformat(),
            from_state=self.state.value,
            to_state=to_state.value,
            reason=reason,
            strategy_version=self.strategy_version,
            idempotency_key=f"{self.trade_id}:{len(self.transitions)}",
            broker_payload=_sanitize(broker_payload or {}),
        )
        self.transitions.append(tr)
        self.state = to_state
        return tr

    @property
    def is_terminal(self) -> bool:
        return not ALLOWED_TRANSITIONS.get(self.state)


_SECRET_KEYS = {"password", "api_key", "apikey", "token", "cst", "x-security-token", "authorization"}


def _sanitize(payload: dict) -> dict:
    """Nettoie le payload broker avant journalisation (jamais de secrets en base)."""
    return {k: ("***" if k.lower() in _SECRET_KEYS else v) for k, v in payload.items()}
