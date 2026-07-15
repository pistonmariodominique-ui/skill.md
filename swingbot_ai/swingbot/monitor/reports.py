"""Rapports quotidien et hebdomadaire (section 7, Monitoring)."""

from __future__ import annotations

from ..journal.journal import Journal


def daily_report(journal: Journal) -> str:
    signals = journal.fetch(
        "SELECT COUNT(*) AS n FROM signals WHERE ts >= date('now')")[0]["n"]
    open_pos = journal.fetch(
        "SELECT COUNT(*) AS n FROM positions WHERE closed_ts IS NULL")[0]["n"]
    closed_today = journal.fetch(
        "SELECT COUNT(*) AS n, COALESCE(SUM(pnl_money),0) AS pnl "
        "FROM positions WHERE closed_ts >= date('now')")[0]
    ks = journal.fetch(
        "SELECT COUNT(*) AS n FROM kill_switch_events WHERE ts >= date('now')")[0]["n"]
    last_eq = journal.fetch(
        "SELECT equity, drawdown_pct FROM risk_snapshots ORDER BY ts DESC LIMIT 1")
    eq_line = (f"equity {last_eq[0]['equity']:.2f}, drawdown {last_eq[0]['drawdown_pct']:.2f}%"
               if last_eq else "equity: n/a")
    return (f"📊 SwingBot — rapport quotidien\n"
            f"{eq_line}\n"
            f"signaux du jour: {signals} | positions ouvertes: {open_pos}\n"
            f"clôturées aujourd'hui: {closed_today['n']} (P&L {closed_today['pnl']:.2f})\n"
            f"événements kill-switch: {ks}")


def weekly_report(journal: Journal) -> str:
    week = journal.fetch(
        "SELECT COUNT(*) AS n, COALESCE(SUM(pnl_money),0) AS pnl, "
        "COALESCE(SUM(swap_paid),0) AS swap, COALESCE(AVG(pnl_r),0) AS avg_r "
        "FROM positions WHERE closed_ts >= date('now','-7 days')")[0]
    by_symbol = journal.fetch(
        "SELECT symbol, COUNT(*) AS n, COALESCE(SUM(pnl_money),0) AS pnl "
        "FROM positions WHERE closed_ts >= date('now','-7 days') "
        "GROUP BY symbol ORDER BY pnl DESC")
    lines = [f"📈 SwingBot — rapport hebdomadaire",
             f"trades clos: {week['n']} | P&L net: {week['pnl']:.2f} | "
             f"swaps: {week['swap']:.2f} | moyenne: {week['avg_r']:.2f}R"]
    for row in by_symbol:
        lines.append(f"  {row['symbol']}: {row['n']} trades, {row['pnl']:.2f}")
    rejected = journal.fetch(
        "SELECT COUNT(*) AS n FROM trade_transitions "
        "WHERE to_state='REJECTED' AND ts >= date('now','-7 days')")[0]["n"]
    lines.append(f"candidats refusés (risque/qualité): {rejected}")
    return "\n".join(lines)
