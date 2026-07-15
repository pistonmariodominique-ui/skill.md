"""Chargement de la configuration (fichier JSON + variables d'environnement).

Zéro dépendance externe : la config est en JSON (config/settings.json).
Les secrets ne vivent JAMAIS dans le fichier de config : uniquement en
variables d'environnement (voir .env.example).
"""

from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .constants import Mode

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "settings.json"


@dataclass
class RiskLimits:
    """Plafonds de risque (section 6.1). Valeurs par défaut = shadow/démo."""
    risk_per_trade_pct: float = 0.50
    max_open_risk_pct: float = 1.50
    max_positions: int = 3
    max_cluster_risk_pct: float = 0.75
    max_daily_loss_pct: float = 1.5
    max_weekly_loss_pct: float = 3.0
    killswitch_drawdown_pct: float = 8.0

    @staticmethod
    def for_mode(mode: Mode, raw: dict) -> "RiskLimits":
        key = "real" if mode == Mode.REAL else "shadow_demo"
        return RiskLimits(**raw.get(key, {}))


@dataclass
class Settings:
    mode: Mode = Mode.SHADOW
    account_currency: str = "EUR"
    initial_equity: float = 10_000.0
    instruments: list[str] = field(default_factory=lambda: [
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
    ])
    risk: RiskLimits = field(default_factory=RiskLimits)
    strategy: dict = field(default_factory=dict)
    backtest: dict = field(default_factory=dict)
    weekend: dict = field(default_factory=dict)
    ai: dict = field(default_factory=dict)
    telegram: dict = field(default_factory=dict)
    broker: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)

    # --- secrets (env uniquement) ---
    @property
    def capital_api_key(self) -> str | None:
        return os.environ.get("CAPITAL_API_KEY")

    @property
    def capital_identifier(self) -> str | None:
        return os.environ.get("CAPITAL_IDENTIFIER")

    @property
    def capital_password(self) -> str | None:
        return os.environ.get("CAPITAL_PASSWORD")

    @property
    def telegram_token(self) -> str | None:
        return os.environ.get("TELEGRAM_BOT_TOKEN")

    @property
    def telegram_chat_id(self) -> str | None:
        return os.environ.get("TELEGRAM_CHAT_ID")

    @property
    def anthropic_api_key(self) -> str | None:
        return os.environ.get("ANTHROPIC_API_KEY")

    @property
    def real_mode_unlocked(self) -> bool:
        """Le mode réel exige une variable d'environnement explicite EN PLUS
        de la checklist Go/No-Go (voir risk/killswitch.py et run.py)."""
        return os.environ.get("SWINGBOT_REAL_MODE_I_ACCEPT_LOSSES") == "YES"


def load_settings(path: Path | None = None, mode_override: str | None = None) -> Settings:
    path = path or CONFIG_PATH
    raw: dict[str, Any] = {}
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
    mode = Mode(mode_override or raw.get("mode", "shadow"))
    settings = Settings(
        mode=mode,
        account_currency=raw.get("account_currency", "EUR"),
        initial_equity=float(raw.get("initial_equity", 10_000.0)),
        instruments=list(raw.get("instruments", Settings().instruments)),
        risk=RiskLimits.for_mode(mode, raw.get("risk", {})),
        strategy=copy.deepcopy(raw.get("strategy", {})),
        backtest=copy.deepcopy(raw.get("backtest", {})),
        weekend=copy.deepcopy(raw.get("weekend", {})),
        ai=copy.deepcopy(raw.get("ai", {})),
        telegram=copy.deepcopy(raw.get("telegram", {})),
        broker=copy.deepcopy(raw.get("broker", {})),
        raw=raw,
    )
    return settings
