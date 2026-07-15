"""Journal applicatif : chaque décision et événement broker est tracé."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..constants import Mode
from ..data.models import Position, Signal
from ..trade.state_machine import Transition
from . import db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Journal:
    def __init__(self, db_path: Path, mode: Mode):
        self.conn = db.connect(db_path)
        self.mode = mode

    # --- signaux -------------------------------------------------------
    def log_signal(self, s: Signal) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO signals VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (s.signal_id, s.ts.isoformat(), s.symbol, s.direction.value,
             s.entry_price, s.stop_price, s.target_price, s.rr_expected,
             s.regime, s.score, json.dumps(s.reasons, ensure_ascii=False),
             json.dumps(s.abstain_reasons, ensure_ascii=False),
             s.strategy_version, self.mode.value))
        self.conn.commit()

    # --- transitions ----------------------------------------------------
    def log_transition(self, trade_id: str, tr: Transition) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO trade_transitions VALUES (?,?,?,?,?,?,?,?)",
            (trade_id, tr.ts, tr.from_state, tr.to_state, tr.reason,
             tr.strategy_version, tr.idempotency_key,
             json.dumps(tr.broker_payload, ensure_ascii=False)))
        self.conn.commit()

    # --- positions -------------------------------------------------------
    def log_position_open(self, trade_id: str, p: Position) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO positions "
            "(position_id, trade_id, symbol, direction, units, entry_price,"
            " stop_price, target_price, opened_ts, risk_money, swap_paid, mode)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (p.position_id, trade_id, p.symbol, p.direction.value, p.units,
             p.entry_price, p.stop_price, p.target_price,
             p.opened_ts.isoformat(), p.risk_money, p.swap_accrued,
             self.mode.value))
        self.conn.commit()

    def log_position_close(self, position_id: str, close_ts: str,
                           close_price: float, pnl_money: float,
                           pnl_r: float, swap_paid: float, reason: str) -> None:
        self.conn.execute(
            "UPDATE positions SET closed_ts=?, close_price=?, pnl_money=?,"
            " pnl_r=?, swap_paid=?, close_reason=? WHERE position_id=?",
            (close_ts, close_price, pnl_money, pnl_r, swap_paid, reason,
             position_id))
        self.conn.commit()

    # --- risque / equity ---------------------------------------------------
    def log_risk_snapshot(self, equity: float, open_risk: float, n_pos: int,
                          daily_pnl_pct: float, weekly_pnl_pct: float,
                          drawdown_pct: float, detail: dict | None = None) -> None:
        self.conn.execute(
            "INSERT INTO risk_snapshots VALUES (?,?,?,?,?,?,?,?)",
            (_now(), equity, open_risk, n_pos, daily_pnl_pct, weekly_pnl_pct,
             drawdown_pct, json.dumps(detail or {}, ensure_ascii=False)))
        self.conn.commit()

    def log_daily_equity(self, date: str, equity: float, pnl_day: float,
                         drawdown_pct: float) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO daily_equity VALUES (?,?,?,?,?)",
            (date, equity, pnl_day, drawdown_pct, self.mode.value))
        self.conn.commit()

    # --- événements ---------------------------------------------------------
    def log_event(self, level: str, source: str, message: str,
                  detail: dict | None = None) -> None:
        self.conn.execute(
            "INSERT INTO system_events VALUES (?,?,?,?,?)",
            (_now(), level, source, message,
             json.dumps(detail or {}, ensure_ascii=False)))
        self.conn.commit()

    def log_killswitch(self, reason: str, detail: str = "") -> None:
        self.conn.execute("INSERT INTO kill_switch_events VALUES (?,?,?)",
                          (_now(), reason, detail))
        self.conn.commit()

    def log_backtest_run(self, strategy_version: str, params: dict,
                         data_hash: str, metrics: dict, passed: bool) -> str:
        run_id = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO backtest_runs VALUES (?,?,?,?,?,?,?)",
            (run_id, _now(), strategy_version,
             json.dumps(params, ensure_ascii=False), data_hash,
             json.dumps(metrics, ensure_ascii=False), int(passed)))
        self.conn.commit()
        return run_id

    # --- lecture (dashboard/rapports) ---------------------------------------
    def fetch(self, sql: str, params: tuple = ()) -> list[dict]:
        cur = self.conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]

    def close(self) -> None:
        self.conn.close()
