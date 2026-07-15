"""AI Analyst (section 9) — rôle strictement consultatif.

L'IA reçoit uniquement des données CLÔTURÉES et structurées, retourne un
JSON validé par schéma. Règles :
- sortie invalide = abstention (l'analyse est ignorée, pas le trade bloqué
  par principe : le moteur déterministe reste seul décideur) ;
- confidence jamais convertie en taille de position ;
- désactivable totalement (ai.enabled=false) sans empêcher la stratégie.

Appel API Anthropic en urllib pour rester sans dépendance.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

VALID_REGIMES = {"bullish", "bearish", "range", "uncertain"}

PROMPT_VERSION = "swing-analyst-v1"

SYSTEM_PROMPT = """Tu es un analyste de marché pour un bot de swing trading.
Tu n'as AUCUN pouvoir de décision : tu classes, résumes et signales les
contradictions. Réponds UNIQUEMENT avec un objet JSON valide au schéma :
{"market_regime": "bullish|bearish|range|uncertain",
 "setup_quality": <entier 0-10>,
 "contradictions": [<chaînes>],
 "event_risks": [<chaînes>],
 "explanation": "<résumé bref>",
 "confidence": <nombre 0.0-1.0>}
N'invente jamais de données absentes du contexte fourni."""


@dataclass
class AnalystReport:
    market_regime: str
    setup_quality: int
    contradictions: list[str]
    event_risks: list[str]
    explanation: str
    confidence: float
    model: str = ""
    prompt_version: str = PROMPT_VERSION


def validate_report(raw: dict) -> AnalystReport | None:
    """Validation stricte du schéma. None = sortie invalide = abstention."""
    try:
        regime = raw["market_regime"]
        if regime not in VALID_REGIMES:
            return None
        quality = int(raw["setup_quality"])
        if not 0 <= quality <= 10:
            return None
        conf = float(raw["confidence"])
        if not 0.0 <= conf <= 1.0:
            return None
        contradictions = list(raw.get("contradictions", []))
        events = list(raw.get("event_risks", []))
        explanation = str(raw.get("explanation", ""))
        return AnalystReport(regime, quality, contradictions, events,
                             explanation, conf)
    except (KeyError, TypeError, ValueError):
        return None


def analyze(context: dict, api_key: str, model: str = "claude-sonnet-5",
            temperature: float = 0.1, timeout: int = 30) -> AnalystReport | None:
    """Appelle l'API Anthropic. Toute erreur => None (abstention silencieuse,
    journalisée par l'appelant). Le contexte ne doit contenir que des
    données clôturées."""
    body = {
        "model": model,
        "max_tokens": 1024,
        "temperature": temperature,
        "system": SYSTEM_PROMPT,
        "messages": [{
            "role": "user",
            "content": ("Contexte marché (données clôturées uniquement) :\n"
                        + json.dumps(context, ensure_ascii=False, indent=2)),
        }],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    try:
        text = payload["content"][0]["text"]
        # Tolère un éventuel bloc markdown autour du JSON.
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            text = text.removeprefix("json").strip()
        raw = json.loads(text)
    except (KeyError, IndexError, json.JSONDecodeError):
        return None

    report = validate_report(raw)
    if report is not None:
        report.model = model
    return report
