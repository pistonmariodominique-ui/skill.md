"""Connecteur Capital.com — héritage ForexBot (section 17).

Implémenté avec urllib (zéro dépendance). Authentification par session
(X-CAP-API-KEY + identifier/password => CST + X-SECURITY-TOKEN).

SÉCURITÉ :
- par défaut, pointe sur l'API DÉMO ;
- l'URL live n'est utilisée que si mode=real ET verrou env levé (run.py) ;
- les secrets viennent exclusivement des variables d'environnement ;
- un ordre n'est confirmé qu'après lecture de la confirmation deal
  (deferred confirmation) avec stop présent.

NOTE : testez d'abord sur compte démo. L'API réelle peut évoluer :
vérifier https://open-api.capital.com/ avant la première connexion.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..constants import Direction
from ..data.models import MAJORS
from .broker_base import Broker, BrokerPosition, OrderRequest, OrderResult

TIMEOUT = 15


@dataclass
class CapitalComBroker(Broker):
    base_url: str
    api_key: str
    identifier: str
    password: str
    cst: str | None = None
    security_token: str | None = None
    _epic_cache: dict[str, dict] = field(default_factory=dict)

    # --- HTTP ---------------------------------------------------------------
    def _request(self, method: str, path: str, body: dict | None = None,
                 auth: bool = True) -> tuple[int, dict, dict]:
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json",
                   "X-CAP-API-KEY": self.api_key}
        if auth:
            if not self.cst:
                self.login()
            headers["CST"] = self.cst or ""
            headers["X-SECURITY-TOKEN"] = self.security_token or ""
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                payload = json.loads(resp.read().decode() or "{}")
                return resp.status, payload, dict(resp.headers)
        except urllib.error.HTTPError as e:
            try:
                payload = json.loads(e.read().decode() or "{}")
            except Exception:
                payload = {}
            return e.code, payload, dict(e.headers or {})
        except (urllib.error.URLError, TimeoutError) as e:
            return 0, {"error": str(e)}, {}

    def login(self) -> bool:
        status, payload, headers = self._request(
            "POST", "/api/v1/session",
            {"identifier": self.identifier, "password": self.password},
            auth=False)
        if status == 200:
            self.cst = headers.get("CST")
            self.security_token = headers.get("X-SECURITY-TOKEN")
            return True
        return False

    # --- interface Broker ------------------------------------------------
    def is_available(self) -> bool:
        status, _, _ = self._request("GET", "/api/v1/time", auth=False)
        return status == 200

    def _market_info(self, symbol: str) -> dict:
        if symbol not in self._epic_cache:
            status, payload, _ = self._request("GET", f"/api/v1/markets/{symbol}")
            self._epic_cache[symbol] = payload if status == 200 else {}
        return self._epic_cache[symbol]

    def min_stop_distance(self, symbol: str) -> float:
        info = self._market_info(symbol)
        rules = (info.get("dealingRules") or {}).get("minStopOrProfitDistance") or {}
        value = float(rules.get("value") or 0)
        unit = rules.get("unit", "POINTS")
        inst = MAJORS.get(symbol)
        if inst and unit == "POINTS":
            return value * inst.pip_size
        # PERCENTAGE ou inconnu : approximation prudente via config statique.
        if inst:
            return inst.min_stop_distance_pips * inst.pip_size
        return 0.0

    def place_order(self, req: OrderRequest) -> OrderResult:
        body = {
            "epic": req.symbol,
            "direction": "BUY" if req.direction == Direction.LONG else "SELL",
            "size": req.units / MAJORS[req.symbol].lot_size if req.symbol in MAJORS else req.units,
            "stopLevel": req.stop_price,
            "guaranteedStop": False,
        }
        if req.target_price:
            body["profitLevel"] = req.target_price
        status, payload, _ = self._request("POST", "/api/v1/positions", body)
        if status != 200 or "dealReference" not in payload:
            return OrderResult(False, error=f"HTTP {status}: {payload}", raw=payload)

        # Confirmation différée OBLIGATOIRE : le deal est-il ouvert, avec stop ?
        ref = payload["dealReference"]
        status, conf, _ = self._request("GET", f"/api/v1/confirms/{ref}")
        if status != 200 or conf.get("dealStatus") != "ACCEPTED":
            return OrderResult(False, error=f"deal non accepté: {conf}", raw=conf)

        deal_id = conf.get("dealId") or (conf.get("affectedDeals") or [{}])[0].get("dealId")
        fill = float(conf.get("level") or 0) or None
        confirmed_stop = conf.get("stopLevel")
        return OrderResult(
            accepted=True, deal_id=deal_id, fill_price=fill,
            confirmed_stop_price=float(confirmed_stop) if confirmed_stop else None,
            stop_confirmed=confirmed_stop is not None,
            raw=conf)

    def modify_stop(self, deal_id: str, new_stop: float) -> bool:
        status, _, _ = self._request("PUT", f"/api/v1/positions/{deal_id}",
                                     {"stopLevel": new_stop})
        return status == 200

    def close_position(self, deal_id: str) -> OrderResult:
        status, payload, _ = self._request("DELETE", f"/api/v1/positions/{deal_id}")
        if status == 200:
            return OrderResult(True, deal_id=deal_id, raw=payload)
        return OrderResult(False, error=f"HTTP {status}: {payload}", raw=payload)

    def list_positions(self) -> list[BrokerPosition]:
        status, payload, _ = self._request("GET", "/api/v1/positions")
        out: list[BrokerPosition] = []
        if status != 200:
            return out
        for item in payload.get("positions", []):
            pos = item.get("position", {})
            market = item.get("market", {})
            symbol = market.get("epic", "")
            lot = MAJORS[symbol].lot_size if symbol in MAJORS else 1.0
            out.append(BrokerPosition(
                deal_id=pos.get("dealId", ""),
                symbol=symbol,
                direction=Direction.LONG if pos.get("direction") == "BUY" else Direction.SHORT,
                units=float(pos.get("size") or 0) * lot,
                entry_price=float(pos.get("level") or 0),
                stop_price=float(pos["stopLevel"]) if pos.get("stopLevel") else None,
                target_price=float(pos["profitLevel"]) if pos.get("profitLevel") else None,
            ))
        return out

    def account_equity(self) -> float:
        status, payload, _ = self._request("GET", "/api/v1/accounts")
        if status != 200:
            return 0.0
        for acc in payload.get("accounts", []):
            if acc.get("preferred"):
                return float((acc.get("balance") or {}).get("balance") or 0)
        return 0.0

    def transactions_since(self, iso_ts: str) -> list[dict]:
        since = iso_ts.replace("+00:00", "").split(".")[0]
        status, payload, _ = self._request(
            "GET", f"/api/v1/history/transactions?from={since}&detailed=true")
        if status != 200:
            return []
        return payload.get("transactions", [])
