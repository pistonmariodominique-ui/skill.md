"""Journal SQLite — tables minimales de la section 10.

SQLite en V1 pour un zip autonome sans dépendance. La couche est isolée
derrière Journal (journal.py) : migrer vers Supabase/Postgres plus tard ne
touche que ce module. UTC partout, données immuables (INSERT only pour les
décisions historiques).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS instruments (
    symbol TEXT PRIMARY KEY, base TEXT, quote TEXT,
    pip_size REAL, lot_size REAL, min_stop_distance_pips REAL
);
CREATE TABLE IF NOT EXISTS candles (
    symbol TEXT, timeframe TEXT, ts TEXT,
    open REAL, high REAL, low REAL, close REAL, volume REAL,
    PRIMARY KEY (symbol, timeframe, ts)
);
CREATE TABLE IF NOT EXISTS signals (
    signal_id TEXT PRIMARY KEY, ts TEXT, symbol TEXT, direction TEXT,
    entry_price REAL, stop_price REAL, target_price REAL,
    rr_expected REAL, regime TEXT, score REAL,
    reasons TEXT, abstain_reasons TEXT, strategy_version TEXT, mode TEXT
);
CREATE TABLE IF NOT EXISTS risk_snapshots (
    ts TEXT, equity REAL, open_risk_money REAL, open_positions INTEGER,
    daily_pnl_pct REAL, weekly_pnl_pct REAL, drawdown_pct REAL, detail TEXT
);
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY, trade_id TEXT, ts TEXT, symbol TEXT,
    direction TEXT, units REAL, entry_price REAL, stop_price REAL,
    target_price REAL, status TEXT, broker_deal_id TEXT,
    idempotency_key TEXT UNIQUE, mode TEXT
);
CREATE TABLE IF NOT EXISTS broker_events (
    ts TEXT, trade_id TEXT, event_type TEXT, payload TEXT
);
CREATE TABLE IF NOT EXISTS positions (
    position_id TEXT PRIMARY KEY, trade_id TEXT, symbol TEXT, direction TEXT,
    units REAL, entry_price REAL, stop_price REAL, target_price REAL,
    opened_ts TEXT, closed_ts TEXT, close_price REAL,
    risk_money REAL, pnl_money REAL, pnl_r REAL, swap_paid REAL,
    close_reason TEXT, mode TEXT
);
CREATE TABLE IF NOT EXISTS transactions (
    tx_id TEXT PRIMARY KEY, ts TEXT, trade_id TEXT, kind TEXT,
    amount REAL, currency TEXT, detail TEXT
);
CREATE TABLE IF NOT EXISTS daily_equity (
    date TEXT PRIMARY KEY, equity REAL, pnl_day REAL, drawdown_pct REAL, mode TEXT
);
CREATE TABLE IF NOT EXISTS swap_costs (
    ts TEXT, position_id TEXT, amount REAL, triple INTEGER
);
CREATE TABLE IF NOT EXISTS strategy_versions (
    version TEXT PRIMARY KEY, name TEXT, params TEXT, created_ts TEXT
);
CREATE TABLE IF NOT EXISTS backtest_runs (
    run_id TEXT PRIMARY KEY, ts TEXT, strategy_version TEXT, params TEXT,
    data_hash TEXT, metrics TEXT, passed_gates INTEGER
);
CREATE TABLE IF NOT EXISTS walk_forward_runs (
    run_id TEXT PRIMARY KEY, ts TEXT, backtest_run_id TEXT,
    fold INTEGER, train_range TEXT, test_range TEXT, metrics TEXT
);
CREATE TABLE IF NOT EXISTS trade_transitions (
    trade_id TEXT, ts TEXT, from_state TEXT, to_state TEXT,
    reason TEXT, strategy_version TEXT, idempotency_key TEXT UNIQUE,
    broker_payload TEXT
);
CREATE TABLE IF NOT EXISTS system_events (
    ts TEXT, level TEXT, source TEXT, message TEXT, detail TEXT
);
CREATE TABLE IF NOT EXISTS kill_switch_events (
    ts TEXT, reason TEXT, detail TEXT
);
CREATE TABLE IF NOT EXISTS notifications (
    ts TEXT, channel TEXT, message TEXT, delivered INTEGER
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
