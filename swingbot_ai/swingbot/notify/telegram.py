"""Notifications Telegram — héritage ForexBot (section 17).

Best-effort : une panne Telegram ne doit JAMAIS bloquer le bot (section 16).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request


def send_telegram(token: str | None, chat_id: str | None, message: str,
                  timeout: int = 10) -> bool:
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message[:4000],
        "parse_mode": "HTML",
    }).encode()
    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, data=data), timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
            return bool(payload.get("ok"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return False


class Notifier:
    """Enveloppe journalisée : chaque notification est tracée en base."""

    def __init__(self, journal, token: str | None, chat_id: str | None,
                 enabled: bool = False):
        self.journal = journal
        self.token = token
        self.chat_id = chat_id
        self.enabled = enabled and bool(token and chat_id)

    def notify(self, message: str) -> None:
        delivered = send_telegram(self.token, self.chat_id, message) if self.enabled else False
        try:
            self.journal.conn.execute(
                "INSERT INTO notifications VALUES (datetime('now'), ?, ?, ?)",
                ("telegram" if self.enabled else "console", message, int(delivered)))
            self.journal.conn.commit()
        except Exception:
            pass
        if not self.enabled:
            print(f"[NOTIF] {message}")
