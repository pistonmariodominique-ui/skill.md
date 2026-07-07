# Backtesting, validation et mise en production

Un backtest ne prouve pas qu'une stratégie gagnera ; il prouve qu'elle n'aurait pas perdu dans le passé SI le test est honnête. 90 % des backtests « incroyables » sont faux. Voici comment faire un test honnête et détecter les faux.

## 1. Backtest honnête : les conditions minimales

- **Frais réels** : commission maker/taker + spread + slippage (min. 0,05–0,1 % par côté en crypto, plus sur les stops exécutés en marché). Un backtest sans frais est nul et non avenu — c'est le piège n° 1, surtout en scalping.
- **Funding** pour les perps sur positions > 8 h.
- **Pas de look-ahead** : toute décision à la bougie N n'utilise que des données closes ≤ N. Les indicateurs qui « repaintent » (ZigZag, fractales non confirmées, Ichimoku futur) sont interdits ou décalés.
- **Exécution pessimiste** : entrée à la clôture de la bougie de signal (pas au meilleur prix de la bougie) ; si stop ET TP touchés dans la même bougie, compter le STOP.
- **Données propres** : ≥ 2–3 ans, incluant au moins un marché haussier, un baissier et un range prolongé. Une stratégie testée uniquement sur 2024–2025 haussier n'a jamais rencontré son pire ennemi.
- **Échantillon** : ≥ 200 trades pour que les statistiques signifient quelque chose (à 50 trades, l'intervalle de confiance du winrate est de ±14 points).

## 2. Métriques à calculer (toutes, pas juste le PnL)

| Métrique | Formule / définition | Seuil sain |
|----------|----------------------|------------|
| Expectancy | (W×gain moyen) − (L×perte moyenne), en R | > 0,2R par trade |
| Profit factor | gains bruts / pertes brutes | > 1,5 (méfiance si > 3 : overfitting probable) |
| Max drawdown | pire baisse peak-to-trough | < 15–20 % |
| Ratio Calmar | rendement annuel / max DD | > 1 |
| Sharpe | rendement excédentaire / volatilité | > 1 |
| Pire série de pertes | consécutives | à comparer au kill-switch |
| Winrate par régime | trend/range/compression séparés | chaque régime activé doit être ≥ 0 en expectancy |
| Stabilité | PnL par trimestre | rentable sur ≥ 70 % des trimestres |

**Le max drawdown historique sera dépassé en réel.** Dimensionner le risque pour survivre à 1,5–2× le DD du backtest.

## 3. Overfitting : le détecter, l'éviter

Symptômes : profit factor > 3–4 ; courbe d'equity presque sans creux ; paramètres très précis (RSI 13,5 ; EMA 47) ; performance qui s'effondre si on change un paramètre de ±10 % ; excellent sur un instrument, mauvais sur les instruments corrélés.

Prévention :
- Peu de paramètres (< 6–8 degrés de liberté pour 200 trades).
- **Test de robustesse** : faire varier chaque paramètre de ±20 %. Une stratégie saine reste rentable sur un plateau de paramètres ; une stratégie overfittée n'est rentable que sur un pic.
- Tester la même stratégie sur 2–3 instruments similaires : l'edge réel se généralise au moins partiellement.
- Ne JAMAIS optimiser sur la totalité de l'historique.

## 4. Walk-forward (la validation qui compte)

1. Découper l'historique en fenêtres glissantes : optimiser sur 12 mois (in-sample), tester sur les 3 mois suivants (out-of-sample), glisser de 3 mois, répéter.
2. La performance réelle attendue = la concaténation des périodes out-of-sample UNIQUEMENT.
3. Critère de validation : l'out-of-sample conserve ≥ 50–60 % de la performance in-sample et reste positif sur la majorité des fenêtres. Sinon : la stratégie n'a pas d'edge stable, retour à la conception.
4. Pour un bot IA : rejouer les payloads loggés à travers le prompt candidat (voir ai-prompt.md) — même protocole in/out-of-sample.

## 5. Protocole de mise en production (jamais de raccourci)

| Étape | Durée / volume | Critère de passage |
|-------|----------------|--------------------|
| 1. Backtest honnête | ≥ 200 trades, 2–3 ans | Métriques du §2 au vert |
| 2. Walk-forward | ≥ 4 fenêtres OOS | §4 validé |
| 3. Paper trading (données live) | ≥ 30 jours ET ≥ 50 trades | Expectancy cohérente avec l'OOS ; zéro bug d'exécution |
| 4. Réel, 10 % du capital prévu | ≥ 1 mois | Slippage/frais réels conformes ; kill-switch jamais contourné |
| 5. Réel, 50 % | ≥ 1 mois | Idem |
| 6. Réel, 100 % | — | Revue mensuelle permanente |

Retour en arrière automatique : si à une étape la performance sort de 2 écarts-types de l'attendu, redescendre d'une étape et investiguer.

## 6. Suivi en production

- Journal automatique : chaque trade avec setup, régime, confidence IA, R réalisé, screenshot/payload.
- Revue mensuelle : expectancy par stratégie/régime/instrument ; calibration de la confidence IA ; comparaison slippage réel vs modélisé.
- **Dégradation d'edge** : si l'expectancy glissante sur 50 trades devient négative alors que le backtest disait positif, le marché a peut-être changé — réduire la taille de moitié, puis stopper si la tendance se confirme. Ne pas « attendre que ça revienne » à taille pleine.
- Recalibrage des paramètres : uniquement lors de la revue planifiée, via walk-forward, jamais en réaction émotionnelle (même algorithmique) à une série de pertes qui est dans la variance normale du système.
