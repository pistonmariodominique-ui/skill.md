# VoltBot ⚡ — Bot de trading haute volatilité (Or, Argent, Gaz naturel)

Bot de trading autonome sur les instruments à **forte volatilité** via **Capital.com**
(compte **DÉMO**), piloté par **Supabase Edge Functions** (Deno/TypeScript) + Gemini + Telegram.

Frère de [ForexBot](https://github.com/pistonmariodominique-ui/ForexBot) — même projet Supabase
(`jarvis-mario`, id `qjnbjslenxsnfrhmlbxn`), mêmes secrets (Capital.com, Gemini, Groq, Telegram,
Finnhub), mais **entités totalement séparées** : tables `volt_*`, fonctions `volt-*`, jobs cron
`volt-*`. VoltBot ne touche à AUCUNE table ni fonction de ForexBot.

## Instruments

| Clé | Epic Capital.com | Marché | Session de trading (Paris) |
|---|---|---|---|
| `GOLD` | GOLD | Or (XAU/USD) | 8h – 22h |
| `SILVER` | SILVER | Argent (XAG/USD) | 8h – 22h |
| `NATURALGAS` | NATURALGAS | Gaz naturel (NYMEX) | 14h – 21h |

## Ce qui est optimisé pour la haute volatilité

- **Tout en ATR, pas de pips fixes** : SL bot = `atr_sl_mult`×ATR(14, M15), TP = `atr_tp_mult`×ATR (R:R 1:2).
- **Filtre de régime de volatilité** : `vol_ratio` = ATR(14) récent / ATR moyen des 200 dernières
  bougies M15. Sous `vol_ratio_min` (0.7) → marché endormi, on ne trade pas. Au-dessus de
  `vol_ratio_max` (3.0) → chaos, on ne trade pas. On trade l'**expansion** de volatilité, pas les extrêmes.
- **Taille de position inversement proportionnelle à la volatilité** : risque € constant par trade
  (`risk_pct` du capital), levier effectif plafonné à 5×.
- **Stop à deux niveaux** : le bot gère ses SL/TP serrés basés ATR via `volt-monitor` (chaque minute) ;
  le **stop GARANTI broker** (minimum ~1% du prix sur l'or) reste posé chez Capital comme filet
  anti-gap/panne. Le sizing se fait sur le stop broker (pire cas réel).
- **Stratégie cassure + momentum** (Donchian 20 + EMA20/50 + RSI + biais EMA200 1H appliqué
  strictement côté code), analyse Gemini 2.5 → 2.0 → Groq en cascade.
- **Blocage news US à fort impact** (fenêtre ±20 min, Finnhub) — l'or et le gaz sur-réagissent.
- **Aucune position overnight** (fermeture 22h Paris) ni week-end (vendredi 19h UTC) — les métaux
  gappent violemment le dimanche soir.
- Garde-fous hérités de ForexBot : verrous anti-doublon, `/confirms` obligatoire (anti-fantômes),
  contrôle de marge pré-trade, circuit breaker quotidien, kill-switch hebdo, quota de trades/jour,
  breakeven à +1×SL, trailing 50% du pic, time-stops 2h/2h30/6h, réconciliation du **P&L réel**
  Capital (`/history/transactions`), adoption des positions orphelines, watchdog.

## Structure

```
voltbot/
  dashboard/index.html      # dashboard (Supabase clé publique, lecture seule + Start/Stop)
  supabase/
    functions/
      volt-trader/          # cron 15 min : analyse + ouverture (v2 déployée)
      volt-monitor/         # cron 1 min : surveillance, fermeture, réconciliation P&L (v1 déployée)
    schema_voltbot.sql      # schéma de référence des tables volt_*
    cron_jobs.sql           # jobs pg_cron (volt-scan, volt-monitor)
```

## Utilisation

1. **Démarrer/arrêter** : ouvrir `dashboard/index.html` (ou le dashboard Lovable) et cliquer
   ▶ Démarrer / ⏸ Arrêter — le bouton bascule `volt_bot_status.is_running`.
2. Le bot analyse toutes les 15 min pendant les sessions, notifie chaque action sur **Telegram**
   (préfixe ⚡ VoltBot, même bot que ForexBot), et journalise tout dans `volt_signals` / `volt_trades`.
3. **Mode diagnostic** (sans trader) : appeler `volt-trader` avec `{"diag": true}` et le header
   `x-cron-secret` → renvoie l'état du compte, des marchés, ATR et vol_ratio.

## Déploiement d'une fonction

```
supabase functions deploy volt-trader --project-ref qjnbjslenxsnfrhmlbxn --no-verify-jwt --use-api
```

## Règle d'or

Compte **DÉMO** jusqu'à validation complète. On optimise l'**expectancy** (€/trade), jamais le
winrate seul. Jamais de martingale, jamais retirer les stops. Les leçons de ForexBot (v72 fantômes,
v107 sizing, v108 minGuaranteedStopDistance) sont intégrées dès la v1.
