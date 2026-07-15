"""Constantes globales : modes d'exécution, états de trade, régimes de marché."""

from enum import Enum


class Mode(str, Enum):
    """Modes d'exécution — parcours obligatoire des specs (section 12)."""
    BACKTEST = "backtest"
    SHADOW = "shadow"      # signaux temps réel, aucun ordre
    DEMO = "demo"          # ordres automatiques sur compte démo dédié
    REAL = "real"          # réel limité — verrouillé par checklist Go/No-Go


class TradeState(str, Enum):
    """Machine d'états d'un trade (section 8 des specs)."""
    CANDIDATE = "CANDIDATE"
    VALIDATED = "VALIDATED"
    RISK_APPROVED = "RISK_APPROVED"
    ORDER_SENT = "ORDER_SENT"
    BROKER_CONFIRMED = "BROKER_CONFIRMED"
    OPEN = "OPEN"
    MANAGED = "MANAGED"
    CLOSED = "CLOSED"
    RECONCILED = "RECONCILED"
    # États d'échec
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    ORDER_FAILED = "ORDER_FAILED"
    PROTECTION_FAILED = "PROTECTION_FAILED"
    DESYNC = "DESYNC"
    EMERGENCY_CLOSED = "EMERGENCY_CLOSED"


# Transitions autorisées — toute autre transition est un bug et lève une erreur.
ALLOWED_TRANSITIONS = {
    TradeState.CANDIDATE: {TradeState.VALIDATED, TradeState.REJECTED, TradeState.EXPIRED},
    TradeState.VALIDATED: {TradeState.RISK_APPROVED, TradeState.REJECTED, TradeState.EXPIRED},
    TradeState.RISK_APPROVED: {TradeState.ORDER_SENT, TradeState.REJECTED, TradeState.EXPIRED},
    TradeState.ORDER_SENT: {TradeState.BROKER_CONFIRMED, TradeState.ORDER_FAILED, TradeState.DESYNC},
    TradeState.BROKER_CONFIRMED: {TradeState.OPEN, TradeState.PROTECTION_FAILED, TradeState.DESYNC},
    TradeState.OPEN: {TradeState.MANAGED, TradeState.CLOSED, TradeState.EMERGENCY_CLOSED, TradeState.DESYNC},
    TradeState.MANAGED: {TradeState.CLOSED, TradeState.EMERGENCY_CLOSED, TradeState.DESYNC},
    TradeState.CLOSED: {TradeState.RECONCILED},
    TradeState.EMERGENCY_CLOSED: {TradeState.RECONCILED},
    TradeState.DESYNC: {TradeState.RECONCILED, TradeState.EMERGENCY_CLOSED},
    # États terminaux
    TradeState.RECONCILED: set(),
    TradeState.REJECTED: set(),
    TradeState.EXPIRED: set(),
    TradeState.ORDER_FAILED: set(),
    TradeState.PROTECTION_FAILED: {TradeState.EMERGENCY_CLOSED, TradeState.RECONCILED},
}


class Regime(str, Enum):
    """Régime de marché Daily (section 5.1)."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    RANGE = "range"
    UNCERTAIN = "uncertain"


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"


class Timeframe(str, Enum):
    H4 = "H4"
    D1 = "D1"
    W1 = "W1"

    @property
    def seconds(self) -> int:
        return {"H4": 4 * 3600, "D1": 24 * 3600, "W1": 7 * 24 * 3600}[self.value]
