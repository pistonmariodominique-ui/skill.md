# VoltBot ⚡ — Chasseur de tendances explosives (haute volatilité)

Bot de trading autonome sur **7 instruments à forte volatilité** via **Capital.com**
(compte **DÉMO**), piloté par **Supabase Edge Functions** (Deno/TypeScript) + Gemini + Telegram.

Frère de [ForexBot](https://github.com/pistonmariodominique-ui/ForexBot) — même projet Supabase
(`jarvis-mario`, id `qjnbjslenxsnfrhmlbxn`), mêmes secrets (Capital.com, Gemini, Groq, Telegram,
Finnhub), mais **entités totalement séparées** : tables `volt_*`, fonctions `volt-*`, jobs cron
`volt-*`. VoltBot ne touche à AUCUNE table ni fonction de ForexBot.

## La stratégie v3 : « trend hunter »

> **Maximiser la volatilité dans le CHOIX des instruments. Minimiser la FRÉQUENCE des trades.**
> Peu de trades, stops serrés, et on laisse courir les gagnants très loin.

Le vrai edge de la volatilité n'est pas la fréquence — c'est la **queue épaisse** : quand l'or
ou le BTC part, il peut filer 5-10×ATR. Un gagnant à 1:6 par semaine écrase vingt scalps à 1:1
(le scalping pur a été chiffré et écarté : le spread mange l'edge, voir la discussion du 12/07).
Conséquence assumée : **winrate bas (35-45 %)**, beaucoup de petites pertes, quelques gros gains.
On juge le bot sur l'**expectancy (€/trade)**, jamais sur le winrate.

## Instruments (epics vérifiés sur le démo le 11/07/2026)

| Clé | Marché | Session d'entrée (Paris) | Week-end |
|---|---|---|---|
| `GOLD` | Or (XAU/USD) | lun-ven 8h–22h | non |
| `SILVER` | Argent (XAG/USD) | lun-ven 8h–22h | non |
| `NATURALGAS` | Gaz naturel (NYMEX) | lun-ven 14h–21h | non |
| `OIL_CRUDE` | Pétrole WTI | lun-ven 10h–21h | non |
| `US30` | Dow Jones (spread 0,004 % !) | lun-ven 14h–22h | non |
| `BTCUSD` | Bitcoin | **24/7** | **oui** |
| `ETHUSD` | Ethereum | **24/7** | **oui** |

Calendrier **par instrument** : plus de blocage week-end global — le crypto trade samedi/dimanche
pendant que le reste dort. Les filtres (spread/ATR, vol_ratio) protègent des conditions pourries
(ex. : spreads crypto élargis le week-end → HOLD automatique).

## Le cycle d'un trade

1. **Thèse M15** (toutes les 5 min, LLM mis en cache 14 min par instrument) : régime EMA20/50,
   RSI, cassure Donchian 20, biais EMA200 1H appliqué strictement par le code, filtre de
   volatilité `vol_ratio` ∈ [0.7, 3.0] — on trade l'expansion, ni le coma ni le chaos.
2. **Entrée affinée M5** : la thèse n'est exécutée que si le M5 confirme (clôture au-delà de
   l'EMA20 M5 + momentum dans le sens). Sinon le bot retente toutes les 5 min pendant 14 min.
3. **SL initial serré** : 2×ATR(M5), borné 0.6–1.5×ATR(M15), jamais < 3×spread. Sizing au risque
   € constant (`risk_pct`) calculé sur le **stop garanti broker** (pire cas réel — leçon v107).
4. **Breakeven à +1×SL** : le trade ne peut plus perdre.
5. **Sortie gagnante = TRAILING ATR (chandelier)** : pas de take-profit — on sort quand le prix
   retrace `trail_atr_mult` (2.5) × ATR depuis le pic. Les gagnants courent (plafond 24h).
6. Garde-fous : time-stops (2h/2h30/6h), fermeture 22h Paris + vendredi soir (instruments
   non-24/7), stop GARANTI broker en filet anti-gap, news US à fort impact bloquées ±20 min,
   circuit breaker quotidien, kill-switch hebdo, quota trades/jour, max 3 positions.
7. **P&L réel** réconcilié depuis `/history/transactions` Capital (pattern ForexBot v38).

## Structure

```
voltbot/
  dashboard/index.html      # dashboard (Supabase clé publique, lecture seule + Start/Stop)
  supabase/
    functions/
      volt-trader/          # cron 5 min : thèse M15 + entrée M5 + ouverture (v3 déployée)
      volt-monitor/         # cron 1 min : trailing ATR, breakeven, time-stops, réconciliation (v3)
    schema_voltbot.sql      # schéma de référence des tables volt_*
    cron_jobs.sql           # jobs pg_cron (volt-scan */5, volt-monitor * * * * *)
```

(Une fonction utilitaire `volt-probe` est aussi déployée : découverte de marchés Capital.com
— recherche d'epics, spreads, horaires — sans jamais trader.)

## Utilisation

1. **Démarrer/arrêter** : dashboard (`dashboard/index.html` ou le projet Lovable « VoltBot
   Dashboard ») → bouton ▶/⏸ qui bascule `volt_bot_status.is_running`.
2. Notifications **Telegram** (préfixe ⚡ VoltBot, même bot que ForexBot ; secret optionnel
   `TELEGRAM_ADMIN_CHAT_ID` pour changer de chat). Journal complet dans `volt_signals` / `volt_trades`.
3. **Mode diagnostic** (sans trader) : appeler `volt-trader` avec `{"diag": true}` et le header
   `x-cron-secret` → compte, marchés, ATR M15/M5, vol_ratio, fenêtre d'entrée par instrument.

## Déploiement d'une fonction

```
supabase functions deploy volt-trader --project-ref qjnbjslenxsnfrhmlbxn --no-verify-jwt --use-api
```

## Règle d'or

Compte **DÉMO** jusqu'à validation complète. On optimise l'**expectancy** (€/trade), jamais le
winrate seul. Jamais de martingale, jamais retirer les stops. Une série de pertes est NORMALE
pour un trend hunter — les limites jour/semaine protègent pendant les séries noires ; couper le
bot après 4 pertes, c'est rater le gagnant qui paie tout. Les leçons de ForexBot (v72 fantômes,
v107 sizing, v108 minGuaranteedStopDistance, v38 réconciliation) sont intégrées.
