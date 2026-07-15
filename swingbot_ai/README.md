# 🌊 SwingBot AI — v1.0

Bot de trading **swing/position semi-autonome** (2 jours à plusieurs semaines), construit d'après `docs/SPECS_SWINGBOT.md` (cahier des charges Mario Piston + Jarvis, v1.0).

> ⚠️ **Avertissement essentiel** — SwingBot AI ne garantit aucun gain et ne supprime pas le risque de perte. Toute performance se mesure après spreads, commissions, slippage, swaps, gaps et fiscalité. N'engagez jamais un capital dont la perte totale serait insupportable. Le passage en réel est volontairement **verrouillé** tant que le parcours backtest → shadow → démo n'est pas validé.

## Installation

**Aucune dépendance** : Python 3.10+ suffit (bibliothèque standard uniquement).

```bash
cd swingbot_ai
python run.py --help
```

## Démarrage rapide (5 minutes)

```bash
# 1. Générer des données synthétiques de test (tuyauterie uniquement !)
python scripts/generate_sample_data.py

# 2. Lancer un backtest complet (coûts, stress x1.5, walk-forward, Monte-Carlo)
python run.py backtest --symbol EURUSD --stress

# 3. Un cycle d'analyse en mode shadow (signaux, aucun ordre)
python run.py cycle --mode shadow

# 4. Le dashboard (lecture seule, 8 écrans)
python run.py dashboard          # http://127.0.0.1:8787

# 5. Les tests (57 tests unitaires et de propriétés)
python -m unittest discover -s tests
```

## Commandes

| Commande | Rôle |
|---|---|
| `python run.py backtest [--symbol X] [--stress]` | Backtest + portes de passage en shadow |
| `python run.py cycle --mode shadow\|demo` | Un cycle d'analyse (cron-friendly, toutes les 4 h) |
| `python run.py loop --mode shadow` | Boucle continue (cycle toutes les 4 h) |
| `python run.py dashboard [--port 8787]` | Dashboard web lecture seule |
| `python run.py checklist` | Checklist Go/No-Go réel (section 13 des specs) |
| `python run.py killswitch [--arm "raison"\|--reset NOM]` | Gestion manuelle du kill-switch |
| `python run.py report [--weekly]` | Rapport quotidien / hebdomadaire |

## Vos données réelles

Déposez vos historiques H4 dans `data/{SYMBOL}_H4.csv` :

```csv
timestamp,open,high,low,close,volume
2018-01-01T00:00:00+00:00,1.20050,1.20180,1.19980,1.20120,3400
```

UTC obligatoire. Visez 8–12 ans d'historique multi-régimes (section 11 des specs) avant toute conclusion. Les données synthétiques du script de génération ne valident **que la tuyauterie**.

## Secrets (jamais dans la config)

Copiez `.env.example`, exportez les variables d'environnement :

- `CAPITAL_API_KEY`, `CAPITAL_IDENTIFIER`, `CAPITAL_PASSWORD` — Capital.com (démo d'abord !)
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — notifications (optionnel)
- `ANTHROPIC_API_KEY` — analyste IA (optionnel, `ai.enabled` dans la config)
- `SWINGBOT_REAL_MODE_I_ACCEPT_LOSSES=YES` — 1ᵉʳ des 3 verrous du mode réel

## Architecture (section 7 des specs)

```
Market Data (CSV/Capital.com) → Data Quality → Feature Engine → Strategy Engine
                                                                     ↓
Journal & Dashboard ← Reconciliation ← Broker ← Execution Engine ← Risk Engine → Kill-switch
```

| Module | Fichiers | Rôle |
|---|---|---|
| Data | `swingbot/data/` | Modèles, qualité (abstention si trous/obsolescence), CSV, resampling H4→D1→W1 |
| Features | `swingbot/features/` | EMA, ATR, ADX, pivots fractals **sans fuite du futur**, structure HH/HL |
| Strategy | `swingbot/strategy/` | Régime Daily + pullback H4 + confirmation à la clôture, R:R net ≥ 2 |
| Risk | `swingbot/risk/` | Sizing sur stop broker réel, plafonds, clusters de devises, kill-switch |
| Execution | `swingbot/execution/` | Broker papier + Capital.com, idempotence, **SL confirmé obligatoire** |
| Trade | `swingbot/trade/` | Machine d'états CANDIDATE→…→RECONCILED, transitions auditées |
| Backtest | `swingbot/backtest/` | Événementiel, coûts réels, swap/triple swap, gaps, walk-forward, Monte-Carlo |
| Reconciliation | `swingbot/reconciliation/` | Broker = source de vérité ; tout écart → kill-switch |
| AI | `swingbot/ai/` | Analyste consultatif JSON validé par schéma — **aucun pouvoir d'ordre** |
| Journal | `swingbot/journal/` | SQLite (tables section 10), UTC, secrets jamais en base |
| Dashboard | `dashboard/` | 8 écrans (section 15), lecture seule |

## Sécurité intégrée (principes non négociables, section 2)

1. **Aucun ordre sans stop-loss broker confirmé** — sinon fermeture d'urgence immédiate (`execution/engine.py`).
2. **Aucune martingale / grid / doublement** — la stratégie ne moyenne jamais et une seule position par symbole.
3. **Sizing sur le stop réellement accepté** — si le broker élargit le stop, le R:R est re-vérifié puis la taille recalculée.
4. **L'IA n'a jamais le pouvoir d'ordre** — sortie JSON invalide = ignorée ; le moteur déterministe décide seul.
5. **Backtest sans fuite du futur** — décision à la clôture de la bougie i, entrée à l'ouverture de i+1 ; pivots utilisables seulement une fois confirmés ; SL prioritaire sur TP intra-bougie.
6. **Mode réel triple-verrouillé** — checklist Go/No-Go verte + variable d'env explicite + double confirmation tapée à la main.
7. **Corrélations agrégées** — EURUSD long + GBPUSD long = une seule exposition USD, plafonnée (stress corrélation 1).
8. **Abstention par défaut** — données incomplètes, prix obsolète, erreur broker ⇒ aucun trade.

## Parcours obligatoire avant argent réel (section 12)

1. **Backtest** : portes = PF ≥ 1.20 hors échantillon, expectancy ≥ 0.10R, ≥ 150 trades, DD conforme, positif à coûts ×1.5, Monte-Carlo p95 sous le plafond, walk-forward stable. Un seul échec = NO-GO.
2. **Shadow 4–8 semaines** : `python run.py loop --mode shadow`.
3. **Démo 8–12 semaines** : `--mode demo` (broker papier ou compte démo Capital.com), zéro désync non expliquée.
4. **Réel limité** : risque 0,25 %/trade, 2 positions max — seulement après `python run.py checklist` 100 % vert.

## Héritage ForexBot (section 17)

Repris et adapté : connexion Capital.com (session CST/X-SECURITY-TOKEN, confirmation différée des deals, lecture des distances minimales de stop), sizing sur stop broker, kill-switch, anti-doublon idempotent, réconciliation par transactions, notifications Telegram, pipeline IA (nouveau prompt, rôle réduit à l'analyse), dashboard.

## Roadmap V1 → V2

- [ ] Brancher un fournisseur de données historiques réelles (8–12 ans)
- [ ] Trailing partiel à 1,5R si le backtest prouve une amélioration robuste (5.3)
- [ ] Calendrier macro (banques centrales, NFP…) avec réduction pré-weekend (6.4)
- [ ] Migration journal SQLite → Supabase (la couche `journal/` est isolée pour ça)
- [ ] Ordres limit sur pullback en plus des ordres market

## Rappel discipline (section 20)

> La meilleure protection contre l'échec est de ne pas confondre une bonne idée, un beau backtest et une preuve de rentabilité réelle.
