"""Boucle live : shadow (signaux sans ordre) et démo (ordres papier/broker).

Cycle d'analyse à la clôture H4 (section 3). Chaque cycle :
1. heartbeat + vérification kill-switch ;
2. chargement + contrôle qualité des données (abstention si KO) ;
3. réconciliation broker (démo/réel) ;
4. gestion des positions ouvertes (break-even, trailing, sorties) ;
5. détection de signaux ; en shadow on journalise SANS ordre ;
6. en démo/réel : risk engine puis execution engine ;
7. snapshot de risque + notifications.

Source de données V1 : fichiers CSV `data/{SYMBOL}_H4.csv` mis à jour par
un job externe (ou l'export du broker). Voir scripts/generate_sample_data.py
pour un jeu de données synthétique de test.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ..config import Settings
from ..constants import Direction, Mode, Timeframe, TradeState
from ..data.models import MAJORS, Position
from ..data.provider import load_csv
from ..data.quality import check_series
from ..execution.broker_base import Broker
from ..execution.engine import ExecutionEngine
from ..features.engine import compute_features
from ..journal.journal import Journal
from ..notify.telegram import Notifier
from ..reconciliation.reconciler import reconcile
from ..risk.killswitch import KillSwitch, evaluate_triggers
from ..risk.limits import check_candidate, open_risk_money
from ..strategy.swing_pullback import StrategyParams, evaluate
from ..trade.state_machine import TradeLifecycle


class LiveRunner:
    def __init__(self, settings: Settings, journal: Journal, broker: Broker,
                 killswitch: KillSwitch, notifier: Notifier,
                 data_dir: Path):
        self.settings = settings
        self.journal = journal
        self.broker = broker
        self.killswitch = killswitch
        self.notifier = notifier
        self.data_dir = data_dir
        self.params = StrategyParams.from_config(settings.strategy)
        self.exec_engine = ExecutionEngine(broker, journal)
        self.open_positions: list[Position] = []
        self.peak_equity = settings.initial_equity
        self.day_start_equity = settings.initial_equity
        self.week_start_equity = settings.initial_equity

    # ------------------------------------------------------------------
    def run_cycle(self) -> dict:
        """Un cycle complet. Retourne un résumé pour le CLI/les tests."""
        now = datetime.now(timezone.utc)
        summary: dict = {"ts": now.isoformat(), "mode": self.settings.mode.value,
                         "signals": [], "orders": [], "abstentions": []}
        self.journal.log_event("info", "runner", "cycle start")

        equity = self._current_equity()
        self.peak_equity = max(self.peak_equity, equity)
        daily_pnl_pct = (equity - self.day_start_equity) / self.day_start_equity * 100
        weekly_pnl_pct = (equity - self.week_start_equity) / self.week_start_equity * 100
        drawdown_pct = (self.peak_equity - equity) / self.peak_equity * 100 if self.peak_equity else 0

        # Réconciliation (démo/réel uniquement — pas de positions en shadow).
        recon_ok = True
        if self.settings.mode in (Mode.DEMO, Mode.REAL):
            report = reconcile(self.open_positions, self.broker)
            recon_ok = report.ok
            if not report.ok:
                self.journal.log_event("error", "reconciliation", report.summary())

        broker_ok = self.broker.is_available()

        # Kill-switch : évaluation systématique des déclencheurs.
        triggers = evaluate_triggers(
            equity, self.peak_equity, daily_pnl_pct, weekly_pnl_pct,
            self.settings.risk, data_ok=True, reconciliation_ok=recon_ok,
            broker_ok=broker_ok)
        if triggers and not self.killswitch.armed:
            for t in triggers:
                self.killswitch.trip(t)
                self.journal.log_killswitch(t)
            self.notifier.notify("🛑 KILL-SWITCH ARMÉ:\n" + "\n".join(triggers))

        # Analyse par instrument.
        for symbol in self.settings.instruments:
            result = self._analyze_symbol(symbol, equity, daily_pnl_pct,
                                          weekly_pnl_pct, now)
            if result:
                summary["signals" if result.get("signal") else "abstentions"].append(result)
                if result.get("order"):
                    summary["orders"].append(result)

        self.journal.log_risk_snapshot(
            equity, open_risk_money(self.open_positions),
            len(self.open_positions), daily_pnl_pct, weekly_pnl_pct,
            drawdown_pct, {"killswitch": self.killswitch.armed})
        summary["equity"] = equity
        summary["killswitch"] = self.killswitch.armed
        return summary

    # ------------------------------------------------------------------
    def _analyze_symbol(self, symbol: str, equity: float,
                        daily_pnl_pct: float, weekly_pnl_pct: float,
                        now: datetime) -> dict | None:
        csv_path = self.data_dir / f"{symbol}_H4.csv"
        if not csv_path.exists():
            self.journal.log_event("warn", "data", f"pas de données pour {symbol}",
                                   {"path": str(csv_path)})
            return {"symbol": symbol, "abstain": "données absentes"}

        candles = load_csv(csv_path, Timeframe.H4)
        quality = check_series(candles, Timeframe.H4, now=now)
        if not quality.ok:
            # Abstention par défaut (principe 10).
            self.journal.log_event("warn", "data_quality",
                                   f"{symbol}: abstention", {"issues": quality.issues})
            return {"symbol": symbol, "abstain": quality.issues[0]}

        fs = compute_features(candles, self.params.ema_fast, self.params.ema_mid,
                              self.params.ema_slow, self.params.atr_period,
                              14, self.params.pivot_lookback)
        inst = MAJORS[symbol]
        est_cost = (inst.typical_spread_pips + 1.0) * inst.pip_size
        signal = evaluate(symbol, inst, fs, self.params, est_cost_price_units=est_cost)
        if signal is None:
            return None

        self.journal.log_signal(signal)
        if not signal.is_actionable:
            return {"symbol": symbol, "signal": False,
                    "abstain": "; ".join(signal.abstain_reasons)}

        out = {"symbol": symbol, "signal": True,
               "direction": signal.direction.value, "rr": signal.rr_expected}

        if self.settings.mode == Mode.SHADOW:
            self.notifier.notify(
                f"👁 SHADOW {symbol} {signal.direction.value.upper()} "
                f"@{signal.entry_price:.5f} SL {signal.stop_price:.5f} "
                f"R:R {signal.rr_expected} — aucun ordre envoyé")
            return out

        # Démo/réel : risk engine puis exécution.
        lifecycle = TradeLifecycle.new(symbol, self.params.version)
        tr = lifecycle.transition(TradeState.VALIDATED,
                                  "setup complet: " + "; ".join(signal.reasons))
        self.journal.log_transition(lifecycle.trade_id, tr)

        risk_money = equity * self.settings.risk.risk_per_trade_pct / 100.0
        candidate = Position(
            position_id="candidate", symbol=symbol, direction=signal.direction,
            units=0, entry_price=signal.entry_price, stop_price=signal.stop_price,
            target_price=signal.target_price, opened_ts=now,
            risk_money=risk_money, risk_r_unit=risk_money)

        decision = check_candidate(
            signal, candidate, self.open_positions, equity,
            self.settings.risk, self.killswitch.armed,
            daily_pnl_pct, weekly_pnl_pct, now,
            self.settings.weekend.get("no_new_entries_friday_after_utc", "15:00"))
        if not decision.approved:
            tr = lifecycle.transition(TradeState.REJECTED, "; ".join(decision.reasons))
            self.journal.log_transition(lifecycle.trade_id, tr)
            out["abstain"] = "; ".join(decision.reasons)
            return out

        tr = lifecycle.transition(TradeState.RISK_APPROVED, "; ".join(decision.reasons))
        self.journal.log_transition(lifecycle.trade_id, tr)

        fx_rates = self._fx_rates_snapshot()
        position = self.exec_engine.execute(
            signal, inst, lifecycle, equity,
            self.settings.risk.risk_per_trade_pct,
            self.settings.account_currency, fx_rates,
            inst.typical_spread_pips, slippage_stress_pips=1.5)
        if position is not None:
            self.open_positions.append(position)
            out["order"] = True
            self.notifier.notify(
                f"✅ {self.settings.mode.value.upper()} {symbol} "
                f"{signal.direction.value.upper()} {position.units:.0f} unités "
                f"@{position.entry_price:.5f} SL confirmé {position.stop_price:.5f}")
        return out

    # ------------------------------------------------------------------
    def _current_equity(self) -> float:
        if self.settings.mode in (Mode.DEMO, Mode.REAL):
            eq = self.broker.account_equity()
            if eq > 0:
                return eq
        return self.settings.initial_equity

    def _fx_rates_snapshot(self) -> dict[str, float]:
        """Taux approximatifs depuis les dernières clôtures disponibles."""
        rates: dict[str, float] = {}
        for symbol in self.settings.instruments:
            csv_path = self.data_dir / f"{symbol}_H4.csv"
            if csv_path.exists():
                candles = load_csv(csv_path, Timeframe.H4)
                if candles:
                    rates[symbol] = candles[-1].close
        return rates
