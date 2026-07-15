#!/usr/bin/env python3
"""SwingBot AI — point d'entrée CLI.

Commandes :
  python run.py backtest [--symbol EURUSD] [--bars 5000] [--stress]
  python run.py cycle    [--mode shadow|demo]      # un cycle d'analyse
  python run.py loop     [--mode shadow|demo]      # boucle continue (4h)
  python run.py dashboard [--port 8787]
  python run.py checklist                          # Go/No-Go réel
  python run.py killswitch [--arm "raison" | --reset OPERATEUR]
  python run.py report   [--weekly]

Le mode réel n'est PAS lançable tant que la checklist n'est pas verte,
que la variable SWINGBOT_REAL_MODE_I_ACCEPT_LOSSES=YES n'est pas posée,
et que la double confirmation interactive n'est pas passée (section 2.8).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from swingbot.config import load_settings
from swingbot.constants import Mode, Timeframe
from swingbot.backtest.costs import CostModel
from swingbot.backtest.engine import run_backtest
from swingbot.backtest.metrics import Gates, check_gates, compute_metrics
from swingbot.backtest.montecarlo import montecarlo_drawdown
from swingbot.backtest.walkforward import degradation_check, run_walk_forward
from swingbot.data.provider import generate_synthetic_h4, load_csv, save_csv
from swingbot.journal.journal import Journal
from swingbot.notify.telegram import Notifier
from swingbot.risk.killswitch import KillSwitch
from swingbot.strategy.swing_pullback import StrategyParams

STATE_DIR = ROOT / "state"
DATA_DIR = ROOT / "data"
DB_PATH = STATE_DIR / "journal.db"
KS_PATH = STATE_DIR / "killswitch.json"


def make_journal(mode: Mode) -> Journal:
    return Journal(DB_PATH, mode)


# ---------------------------------------------------------------- backtest
def cmd_backtest(args) -> int:
    settings = load_settings(mode_override="backtest")
    params = StrategyParams.from_config(settings.strategy)
    bt_cfg = settings.backtest
    journal = make_journal(Mode.BACKTEST)

    symbols = [args.symbol] if args.symbol else settings.instruments
    all_metrics = {}
    for symbol in symbols:
        csv_path = DATA_DIR / f"{symbol}_H4.csv"
        if csv_path.exists():
            candles = load_csv(csv_path, Timeframe.H4)
            source = str(csv_path)
        else:
            print(f"⚠ {symbol}: pas de CSV dans data/ — données SYNTHÉTIQUES "
                  f"(valident la tuyauterie, PAS la stratégie)")
            candles = generate_synthetic_h4(
                symbol, datetime(2018, 1, 1, tzinfo=timezone.utc), args.bars,
                seed=args.seed)
            source = "synthetic"
        if len(candles) < 400:
            print(f"✗ {symbol}: historique insuffisant ({len(candles)} bougies)")
            continue

        def build_costs(stress: float) -> CostModel:
            return CostModel(
                spread_pips_base=bt_cfg.get("spread_pips_base", 1.0),
                spread_pips_stress=bt_cfg.get("spread_pips_stress", 2.5),
                slippage_pips_max=bt_cfg.get("slippage_pips_max", 1.0),
                commission_per_lot=bt_cfg.get("commission_per_lot", 0.0),
                swap_long_pips_per_day=bt_cfg.get("swap_long_pips_per_day", -0.55),
                swap_short_pips_per_day=bt_cfg.get("swap_short_pips_per_day", -0.25),
                stress_multiplier=stress, seed=args.seed)

        print(f"\n=== {symbol} ({len(candles)} bougies H4, source: {source}) ===")
        t0 = time.time()
        result = run_backtest(symbol, candles, params, build_costs(1.0),
                              settings.initial_equity)
        metrics = compute_metrics(result)
        print(f"backtest en {time.time()-t0:.1f}s — {metrics['n_trades']} trades")

        stressed_metrics = None
        if args.stress:
            stressed = run_backtest(symbol, candles, params, build_costs(
                bt_cfg.get("cost_stress_multiplier", 1.5)),
                settings.initial_equity)
            stressed_metrics = compute_metrics(stressed)

        mc = montecarlo_drawdown([t.pnl_money for t in result.trades],
                                 settings.initial_equity,
                                 runs=bt_cfg.get("monte_carlo_runs", 1000))
        folds = run_walk_forward(symbol, candles, params, build_costs(1.0),
                                 settings.initial_equity,
                                 bt_cfg.get("walk_forward_train_bars", 1500),
                                 bt_cfg.get("walk_forward_test_bars", 375))
        wf_ok, wf_msg = degradation_check(folds)

        passed, fails = check_gates(metrics, Gates(),
                                    stressed_metrics=stressed_metrics,
                                    mc_p95_drawdown=mc["p95"])
        if not wf_ok:
            passed = False
            fails.append(f"walk-forward: {wf_msg}")

        data_hash = hashlib.sha256(
            f"{source}:{len(candles)}:{candles[-1].ts.isoformat()}".encode()
        ).hexdigest()[:16]
        journal.log_backtest_run(params.version, params.__dict__, data_hash,
                                 {**metrics, "monte_carlo": mc,
                                  "walk_forward": wf_msg,
                                  "stressed": stressed_metrics}, passed)

        for k in ("n_trades", "net_return_pct", "profit_factor", "expectancy_r",
                  "win_rate", "max_drawdown_pct", "sharpe", "total_swap", "total_costs"):
            print(f"  {k:20s} {metrics.get(k)}")
        print(f"  monte_carlo_p95_dd   {mc['p95']}%")
        print(f"  walk_forward         {wf_msg}")
        if stressed_metrics:
            print(f"  stress x1.5 return   {stressed_metrics['net_return_pct']}%")
        print(f"  PORTES SHADOW        {'✅ PASS' if passed else '❌ NO-GO'}")
        for f in fails:
            print(f"    ✗ {f}")
        all_metrics[symbol] = metrics

    journal.close()
    return 0


# ---------------------------------------------------------------- live
def cmd_cycle(args, loop: bool = False) -> int:
    mode = Mode(args.mode)
    if mode == Mode.REAL and not _real_mode_gate():
        return 1

    settings = load_settings(mode_override=mode.value)
    journal = make_journal(mode)
    killswitch = KillSwitch.load(KS_PATH)
    notifier = Notifier(journal, settings.telegram_token,
                        settings.telegram_chat_id,
                        settings.telegram.get("enabled", False))

    if mode in (Mode.DEMO, Mode.REAL) and settings.broker.get("provider") == "capital":
        from swingbot.execution.capital_com import CapitalComBroker
        base = settings.broker["capital_base_url_live"] if mode == Mode.REAL \
            else settings.broker["capital_base_url_demo"]
        if not all([settings.capital_api_key, settings.capital_identifier,
                    settings.capital_password]):
            print("✗ secrets Capital.com absents (CAPITAL_API_KEY / "
                  "CAPITAL_IDENTIFIER / CAPITAL_PASSWORD)")
            return 1
        broker = CapitalComBroker(base, settings.capital_api_key,
                                  settings.capital_identifier,
                                  settings.capital_password)
    else:
        from swingbot.execution.paper_broker import PaperBroker
        broker = PaperBroker(equity=settings.initial_equity)

    from swingbot.live.runner import LiveRunner
    runner = LiveRunner(settings, journal, broker, killswitch, notifier, DATA_DIR)

    while True:
        summary = runner.run_cycle()
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        if not loop:
            break
        print("prochain cycle dans 4h (Ctrl+C pour arrêter)…")
        try:
            time.sleep(4 * 3600)
        except KeyboardInterrupt:
            break
    journal.close()
    return 0


def _real_mode_gate() -> bool:
    """Triple verrou du mode réel (principe 8)."""
    settings = load_settings()
    if not settings.real_mode_unlocked:
        print("✗ mode réel verrouillé : poser SWINGBOT_REAL_MODE_I_ACCEPT_LOSSES=YES")
        return False
    ok, items = run_checklist()
    if not ok:
        print("✗ checklist Go/No-Go non verte — NO-GO :")
        for label, passed, detail in items:
            if not passed:
                print(f"    ✗ {label}: {detail}")
        return False
    answer = input("⚠ CONFIRMATION 1/2 — taper exactement 'JE COMPRENDS LES RISQUES': ")
    if answer.strip() != "JE COMPRENDS LES RISQUES":
        return False
    answer = input("⚠ CONFIRMATION 2/2 — taper exactement 'ACTIVER REEL': ")
    if answer.strip() != "ACTIVER REEL":
        return False
    return True


# ---------------------------------------------------------------- checklist
def run_checklist() -> tuple[bool, list[tuple[str, bool, str]]]:
    """Checklist Go/No-Go (section 13). Un seul échec = NO-GO."""
    journal = make_journal(Mode.SHADOW)
    items: list[tuple[str, bool, str]] = []

    bt = journal.fetch("SELECT passed_gates FROM backtest_runs ORDER BY ts DESC LIMIT 1")
    items.append(("backtest récent avec portes PASS",
                  bool(bt and bt[0]["passed_gates"]),
                  "aucun backtest PASS enregistré" if not (bt and bt[0]["passed_gates"]) else "ok"))

    fwd = journal.fetch(
        "SELECT COUNT(*) AS n, COALESCE(AVG(pnl_r),0) AS avg_r FROM positions "
        "WHERE closed_ts IS NOT NULL AND mode IN ('shadow','demo')")[0]
    items.append((f"≥ 50 trades forward (actuel: {fwd['n']})", fwd["n"] >= 50,
                  "pas assez de trades shadow/démo"))
    items.append((f"expectancy forward positive ({fwd['avg_r']:.2f}R)",
                  fwd["n"] > 0 and fwd["avg_r"] > 0, "expectancy non positive"))

    ks = KillSwitch.load(KS_PATH)
    items.append(("kill-switch désarmé", not ks.armed, "kill-switch armé"))
    tested = any(e.reason == "manual_test" for e in ks.events)
    items.append(("kill-switch testé (run.py killswitch --arm manual_test puis --reset)",
                  tested, "aucun test manuel tracé"))

    incidents = journal.fetch(
        "SELECT COUNT(*) AS n FROM system_events WHERE level='error' "
        "AND ts >= datetime('now','-30 days')")[0]["n"]
    items.append((f"aucun incident critique sur 30 jours (actuel: {incidents})",
                  incidents == 0, f"{incidents} erreurs sur 30 jours"))

    journal.close()
    return all(p for _, p, _ in items), items


def cmd_checklist(_args) -> int:
    ok, items = run_checklist()
    print("Checklist Go/No-Go réel (section 13) — un seul échec = NO-GO\n")
    for label, passed, detail in items:
        print(f"  {'✅' if passed else '❌'} {label}" + ("" if passed else f" — {detail}"))
    print(f"\nRésultat : {'🟢 GO possible (verrous env + double confirmation restants)' if ok else '🔴 NO-GO'}")
    return 0 if ok else 1


# ---------------------------------------------------------------- divers
def cmd_killswitch(args) -> int:
    ks = KillSwitch.load(KS_PATH)
    if args.arm:
        ks.trip(args.arm, "armement manuel CLI")
        print(f"🛑 kill-switch ARMÉ ({args.arm})")
    elif args.reset:
        ks.reset_manual(args.reset)
        print(f"✅ kill-switch désarmé par {args.reset}")
    else:
        print(f"kill-switch: {'ARMÉ' if ks.armed else 'désarmé'}")
        for e in ks.events[-5:]:
            print(f"  {e.ts} {e.reason} {e.detail}")
    return 0


def cmd_dashboard(args) -> int:
    sys.path.insert(0, str(ROOT / "dashboard"))
    from dashboard.server import serve
    serve(port=args.port)
    return 0


def cmd_report(args) -> int:
    from swingbot.monitor.reports import daily_report, weekly_report
    journal = make_journal(Mode.SHADOW)
    print(weekly_report(journal) if args.weekly else daily_report(journal))
    journal.close()
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="swingbot", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("backtest")
    b.add_argument("--symbol")
    b.add_argument("--bars", type=int, default=5000)
    b.add_argument("--seed", type=int, default=42)
    b.add_argument("--stress", action="store_true",
                   help="ajoute le test coûts x1.5")

    for name in ("cycle", "loop"):
        c = sub.add_parser(name)
        c.add_argument("--mode", default="shadow",
                       choices=["shadow", "demo", "real"])

    d = sub.add_parser("dashboard")
    d.add_argument("--port", type=int, default=8787)

    sub.add_parser("checklist")

    k = sub.add_parser("killswitch")
    k.add_argument("--arm", metavar="RAISON")
    k.add_argument("--reset", metavar="OPERATEUR")

    r = sub.add_parser("report")
    r.add_argument("--weekly", action="store_true")

    args = p.parse_args()
    STATE_DIR.mkdir(exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)

    return {
        "backtest": cmd_backtest,
        "cycle": lambda a: cmd_cycle(a, loop=False),
        "loop": lambda a: cmd_cycle(a, loop=True),
        "dashboard": cmd_dashboard,
        "checklist": cmd_checklist,
        "killswitch": cmd_killswitch,
        "report": cmd_report,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
