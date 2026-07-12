# 📈 Plan d'amélioration VoltBot — marche à suivre RIGOUREUSE

> **La règle qui domine toutes les autres : UN SEUL changement à la fois, avec un
> échantillon suffisant avant de juger.** L'ennemi n°1 d'un bot n'est pas le marché,
> c'est son propriétaire qui bidouille les réglages après 3 pertes. ForexBot a appris
> ça à la dure (75 trades de leçons) — VoltBot doit le faire proprement dès le départ.

## Les 3 métriques qui comptent (dans cet ordre)

| Métrique | Formule | Objectif |
|---|---|---|
| **Expectancy** | P&L total ÷ nb de trades propres | **> 0 €** puis croissante |
| **Profit factor** | Σ gains ÷ Σ pertes (valeur absolue) | > 1.3 |
| **Max drawdown** | Pire série de pertes cumulées | < 15 % du capital |

Le winrate NE compte PAS seul : un trend hunter gagne avec 35-45 % de réussite.
Un winrate qui monte pendant que l'expectancy baisse = le bot coupe ses gagnants trop tôt.

⚠️ Ne compter QUE les trades `is_clean_trade = true` et `pnl_reconciled = true`
(P&L réel Capital, fantômes exclus).

---

## Palier 0 — BASELINE (semaines 1-2) : ne touche à RIEN

**Objectif : ≥ 30 trades propres, réglages d'usine.**

- Bot ON, `risk_pct = 0.5`, tous les instruments actifs.
- Interdiction absolue de modifier un réglage — même si ça perd. Les limites
  jour (-20 €) et semaine (-60 €) sont tes seuls fusibles, et ils suffisent.
- Chaque dimanche : remplir le `JOURNAL-TEMPLATE.md` avec les requêtes ci-dessous.

**Requête maîtresse — tableau de bord par instrument** (SQL Editor Supabase) :
```sql
SELECT instrument,
  COUNT(*)                                              AS trades,
  ROUND(SUM(profit_loss)::numeric, 2)                   AS pnl_total,
  ROUND(AVG(profit_loss)::numeric, 2)                   AS expectancy,
  ROUND(100.0 * COUNT(*) FILTER (WHERE profit_loss > 0) / COUNT(*), 0) AS winrate_pct,
  ROUND(AVG(profit_loss) FILTER (WHERE profit_loss > 0)::numeric, 2)   AS gain_moyen,
  ROUND(AVG(profit_loss) FILTER (WHERE profit_loss < 0)::numeric, 2)   AS perte_moyenne,
  ROUND((SUM(profit_loss) FILTER (WHERE profit_loss > 0) /
         NULLIF(ABS(SUM(profit_loss) FILTER (WHERE profit_loss < 0)), 0))::numeric, 2) AS profit_factor
FROM volt_trades
WHERE status = 'CLOSED' AND is_clean_trade = true AND pnl_reconciled = true
GROUP BY instrument ORDER BY pnl_total DESC;
```

**Analyse des sorties — le trailing fait-il son travail ?**
```sql
SELECT close_reason, COUNT(*) AS n,
  ROUND(AVG(profit_loss)::numeric, 2) AS pnl_moyen,
  ROUND(AVG(max_pnl_points / NULLIF(atr_at_open, 0))::numeric, 1) AS pic_moyen_en_atr
FROM volt_trades
WHERE status = 'CLOSED' AND is_clean_trade = true
GROUP BY close_reason ORDER BY n DESC;
```

**Sortie du palier** : 30 trades propres → passe au Palier 1. Pas avant.

---

## Palier 1 — ÉLAGAGE DES INSTRUMENTS (semaines 3-4)

**Un instrument se mérite.** Avec ≥ 10 trades propres sur un instrument :
- Expectancy **< -0,5 €/trade** → **désactive-le** (retire-le de `volt_settings.instruments`).
- Expectancy entre -0,5 et 0 → sursis de 10 trades supplémentaires.
- Ne JAMAIS désactiver un instrument avec < 10 trades (bruit statistique).

```sql
UPDATE volt_settings SET instruments = ARRAY['GOLD','US30','BTCUSD']  -- exemple
WHERE true;
```
Note la décision + la date dans le journal. Un instrument coupé peut être réessayé
3 mois plus tard (les régimes de marché changent).

---

## Palier 2 — CALIBRATION DE LA CONFIANCE LLM (semaines 5-6)

Le LLM annonce une confiance : vérifie qu'elle veut dire quelque chose.
```sql
SELECT width_bucket(s.confidence, 0.65, 0.95, 3) AS tranche,
  MIN(s.confidence) AS conf_min, MAX(s.confidence) AS conf_max,
  COUNT(t.id) AS trades, ROUND(AVG(t.profit_loss)::numeric, 2) AS expectancy
FROM volt_signals s
JOIN volt_trades t ON t.instrument = s.instrument AND s.executed = true
  AND t.opened_at BETWEEN s.created_at - interval '2 min' AND s.created_at + interval '10 min'
WHERE t.status = 'CLOSED' AND t.is_clean_trade = true
GROUP BY 1 ORDER BY 1;
```
- Si la tranche haute (≥ 0.80) surperforme nettement → monte `min_confidence` à 0.75.
- Si les tranches sont plates → la confiance n'apporte rien, laisse 0.70 et
  compte sur le VoltScore (Palier 4).
**Un seul changement, puis 20 trades d'observation.**

---

## Palier 3 — RÉGLAGE DU TRAILING (semaines 7-10)

La sortie est LE levier du trend hunter. Question : 2.5×ATR laisse-t-il assez courir ?
- `pic_moyen_en_atr` (requête Palier 0) **> 4** sur les sorties trailing → le
  marché va plus loin que ce qu'on capture → teste `trail_atr_mult = 3.0`.
- Beaucoup de sorties « Breakeven » avec pic ≈ 1×SL → trailing trop lâche au
  début → teste 2.0.
```sql
UPDATE volt_settings SET trail_atr_mult = 3.0 WHERE true;  -- UN test à la fois
```
**Protocole : 2 semaines OU 20 trades par valeur testée, puis compare l'expectancy.
Garde la meilleure, note tout.**

---

## Palier 4 — VOLTSCORE EN SHADOW PUIS EN FILTRE (semaines 8-12)

1. **Shadow (aucun impact)** : brancher `volt-score.ts` dans volt-trader pour loguer
   le score dans `volt_signals.reasoning` (préfixe `[VS:78]`) à chaque analyse.
2. Après ≥ 30 trades avec score logué :
```sql
SELECT CASE WHEN s.reasoning ~ '\[VS:(7[0-9]|8[0-9]|9[0-9]|100)\]' THEN 'A+ (>=70)'
            WHEN s.reasoning ~ '\[VS:(5[5-9]|6[0-9])\]' THEN 'B (55-69)'
            ELSE '< 55' END AS bucket,
  COUNT(t.id) AS trades, ROUND(AVG(t.profit_loss)::numeric, 2) AS expectancy
FROM volt_signals s
JOIN volt_trades t ON t.instrument = s.instrument AND s.executed = true
  AND t.opened_at BETWEEN s.created_at - interval '2 min' AND s.created_at + interval '10 min'
WHERE t.status = 'CLOSED' AND t.is_clean_trade = true
GROUP BY 1;
```
3. Si les A+ surperforment clairement → activer le filtre dur : n'exécuter que
   score ≥ 70 (ou ≥ 55 avec confiance LLM ≥ 0.80). Sinon, le VoltScore reste un
   outil de lecture TradingView et on n'ajoute PAS de complexité au bot.

---

## Palier 5 — MONTÉE EN RISQUE (mois 3+)

Conditions TOUTES remplies sur les 50 derniers trades propres :
- Profit factor > 1.3 ✚ expectancy > 0 ✚ drawdown max < 10 %
→ `risk_pct` 0.5 → **0.75**. Re-validation sur 30 trades → **1.0** (plafond du code).

Si le profit factor retombe < 1.1 après la montée → redescends immédiatement.
La montée en risque AMPLIFIE ce qui existe : n'amplifie jamais un système négatif.

---

## Les interdits permanents

1. ❌ Deux changements en même temps (tu ne sauras jamais lequel a agi).
2. ❌ Juger sur < 20 trades ou < 2 semaines.
3. ❌ Modifier quoi que ce soit pendant un drawdown (les fusibles jour/semaine gèrent).
4. ❌ Retirer les stops, élargir un SL en cours de trade, moyenner un perdant.
5. ❌ Passer en `live` avant les critères de STRATEGIE-MAX.md.
6. ❌ Désactiver le filtre 1H ou le filtre de volatilité « pour voir ».
