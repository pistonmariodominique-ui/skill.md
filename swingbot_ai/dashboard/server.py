"""Dashboard SwingBot AI — serveur HTTP stdlib, lecture seule sur le journal.

Lancement : python run.py dashboard  (ou python dashboard/server.py)
Le dashboard ne peut PAS passer d'ordre ni changer le mode : lecture seule.
Le kill-switch manuel et le désarmement passent par le CLI, volontairement.
"""

from __future__ import annotations

import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT.parent / "state" / "journal.db"
INDEX = ROOT / "index.html"

QUERIES = {
    "overview": (
        "SELECT ts, equity, open_risk_money, open_positions, daily_pnl_pct,"
        " weekly_pnl_pct, drawdown_pct FROM risk_snapshots ORDER BY ts DESC LIMIT 1"),
    "equity_curve": (
        "SELECT ts, equity FROM risk_snapshots ORDER BY ts ASC LIMIT 2000"),
    "signals": (
        "SELECT ts, symbol, direction, entry_price, stop_price, rr_expected,"
        " regime, score, reasons, abstain_reasons, mode FROM signals"
        " ORDER BY ts DESC LIMIT 100"),
    "positions": (
        "SELECT symbol, direction, units, entry_price, stop_price, target_price,"
        " opened_ts, closed_ts, close_price, risk_money, pnl_money, pnl_r,"
        " swap_paid, close_reason, mode FROM positions ORDER BY opened_ts DESC LIMIT 200"),
    "transitions": (
        "SELECT trade_id, ts, from_state, to_state, reason FROM trade_transitions"
        " ORDER BY ts DESC LIMIT 200"),
    "events": (
        "SELECT ts, level, source, message, detail FROM system_events"
        " ORDER BY ts DESC LIMIT 200"),
    "killswitch": (
        "SELECT ts, reason, detail FROM kill_switch_events ORDER BY ts DESC LIMIT 50"),
    "backtests": (
        "SELECT run_id, ts, strategy_version, metrics, passed_gates"
        " FROM backtest_runs ORDER BY ts DESC LIMIT 20"),
    "daily_equity": (
        "SELECT date, equity, pnl_day, drawdown_pct, mode FROM daily_equity"
        " ORDER BY date ASC LIMIT 1000"),
}


def query(sql: str) -> list[dict]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql).fetchall()]
    finally:
        conn.close()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            body = INDEX.read_bytes()
            self._send(200, body, "text/html; charset=utf-8")
        elif path.startswith("/api/"):
            key = path.removeprefix("/api/")
            if key not in QUERIES:
                self._send(404, b'{"error":"inconnu"}', "application/json")
                return
            data = query(QUERIES[key])
            self._send(200, json.dumps(data, ensure_ascii=False).encode(),
                       "application/json; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain")

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # silencieux


def serve(host: str = "127.0.0.1", port: int = 8787):
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Dashboard SwingBot AI : http://{host}:{port}  (Ctrl+C pour arrêter)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    serve()
