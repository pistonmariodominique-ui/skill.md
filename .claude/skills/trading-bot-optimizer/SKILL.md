---
name: trading-bot-optimizer
description: "Optimisation de la rentabilité d'un bot de trading : stratégie, indicateurs, effet de levier, analyse graphique multi-timeframe, prompt IA pour la gestion des trades, gestion du risque, backtesting et walk-forward. Actions : concevoir, optimiser, auditer, backtester, améliorer un bot de trading (crypto, forex, actions, futures). Sujets : winrate, expectancy, risk/reward, position sizing, Kelly, drawdown, stop-loss, take-profit, trailing stop, RSI, EMA, MACD, ATR, volume profile, order blocks, market structure, régimes de marché, overfitting, walk-forward, paper trading. Utiliser ce skill dès qu'on travaille sur un bot de trading, une stratégie de trading ou un prompt IA de trading."
---

# Trading Bot Optimizer — Rentabilité & Gestion du Risque

Skill d'optimisation d'un bot de trading algorithmique/IA. Couvre la chaîne complète : régime de marché → stratégie → indicateurs → analyse graphique → décision IA → sizing/levier → exécution → journal → backtesting → amélioration continue.

## ⚠️ Principe fondateur (à lire en premier)

**Un winrate de 100 % n'existe pas et ne doit jamais être l'objectif.** Tout système qui le promet est soit sur-optimisé (overfitting), soit une martingale qui explose, soit une arnaque. La rentabilité vient de l'**espérance de gain (expectancy)**, pas du winrate :

```
Expectancy = (Winrate × Gain moyen) − (Lossrate × Perte moyenne)
```

Un bot à 45 % de winrate avec un ratio risk/reward de 1:2,5 est **très rentable**. Un bot à 90 % de winrate qui rend tout sur une seule perte est **ruineux**. Ce skill maximise l'expectancy et la survie du capital — c'est ainsi qu'on « fait grimper » la performance réelle.

Objectifs réalistes et sains :
- Winrate 45–65 % selon le style (trend-following bas, mean-reversion haut)
- Risk/Reward moyen ≥ 1:1,5 (viser 1:2 à 1:3)
- Profit factor > 1,5 ; Sharpe > 1 ; Max drawdown < 15–20 %
- **Survie du capital avant tout** : on ne peut pas trader demain avec un compte à zéro

## Quand appliquer ce skill

- Conception ou refonte d'un bot de trading (crypto, forex, indices, actions)
- Écriture/optimisation du prompt système d'une IA qui prend les décisions de trade
- Choix des indicateurs, timeframes, filtres d'entrée/sortie
- Calibrage du levier, du position sizing, des stops
- Audit d'un bot existant qui perd de l'argent ou a un drawdown excessif
- Mise en place d'un backtest, walk-forward ou paper trading

## Architecture de décision (pipeline obligatoire)

Toute décision de trade doit traverser ces 7 couches, dans l'ordre. Une couche qui dit NON = pas de trade. **Ne pas trader est une position.**

| # | Couche | Rôle | Référence |
|---|--------|------|-----------|
| 1 | Régime de marché | Trend / range / haute volatilité / news — choisit la stratégie active | `references/strategy.md` |
| 2 | Analyse graphique multi-timeframe | Structure, niveaux, contexte HTF → LTF | `references/chart-analysis.md` |
| 3 | Confluence d'indicateurs | 2–4 indicateurs **non redondants** confirment | `references/indicators.md` |
| 4 | Filtres de veto | News, spread, liquidité, corrélation, session | `references/risk-management.md` |
| 5 | Décision IA structurée | Prompt strict, sortie JSON, score de confiance | `references/ai-prompt.md` |
| 6 | Sizing & levier | Risque fixe par trade, levier dérivé du stop (jamais l'inverse) | `references/risk-management.md` |
| 7 | Gestion de la position | SL/TP/BE/trailing définis AVANT l'entrée, jamais élargis | `references/risk-management.md` |

## Les 10 règles d'or (non négociables)

1. **Risque fixe par trade : 0,5–2 % du capital, jamais plus.** Le sizing se calcule à partir de la distance du stop, pas d'un montant arbitraire.
2. **Le levier est une conséquence, pas un choix.** `taille = (capital × %risque) / distance_stop` ; le levier n'est que le moyen d'atteindre cette taille. Levier effectif max recommandé : 3–5× crypto, 5–10× forex majeurs.
3. **Stop-loss obligatoire sur chaque trade, placé selon la structure (ATR/swing), jamais déplacé contre soi.**
4. **R:R minimum 1:1,5 vérifié avant l'entrée**, sinon pas de trade.
5. **Kill-switch de drawdown** : −3 % jour → stop 24 h ; −6 % semaine → stop 7 j ; −10 % mois → arrêt total et audit. Le bot doit l'implémenter en dur, pas dans le prompt.
6. **Jamais de martingale, jamais de moyenne à la baisse sur une position perdante, jamais de position sans stop.**
7. **Une stratégie = un régime de marché.** Détecter le régime d'abord ; trader un range avec une stratégie de tendance est la première cause de pertes.
8. **Confluence, pas accumulation** : 2–4 signaux indépendants (tendance + momentum + volume/volatilité). 6 indicateurs corrélés = 1 seul signal déguisé.
9. **Tout changement passe par backtest → walk-forward → paper trading → petit capital réel.** Jamais de modification directe en production.
10. **Journal de trades exhaustif** (setup, régime, confiance IA, résultat, screenshot). Sans données, pas d'amélioration possible.

## Workflow d'optimisation d'un bot existant

1. **Audit** : lire le code/les prompts ; vérifier chaque règle d'or ; identifier celles violées (le plus souvent : sizing variable, pas de kill-switch, indicateurs redondants, prompt IA vague).
2. **Mesurer** : reconstituer expectancy, profit factor, max DD, distribution des R par setup et par régime de marché à partir de l'historique.
3. **Couper** : désactiver les setups/régimes à expectancy négative avant d'ajouter quoi que ce soit.
4. **Renforcer** : durcir le risque (règles 1–6), structurer le prompt IA (`references/ai-prompt.md`), ajouter la détection de régime.
5. **Valider** : backtest avec frais/slippage réalistes, walk-forward, puis paper trading ≥ 30 jours ou ≥ 100 trades (`references/backtesting.md`).
6. **Déployer progressivement** : 10 % du capital prévu → 50 % après un mois conforme → 100 %.
7. **Boucle mensuelle** : revue du journal, recalibrage des paramètres UNIQUEMENT via walk-forward, jamais à chaud après une série de pertes.

## Fichiers de référence

| Fichier | Contenu |
|---------|---------|
| `references/strategy.md` | Régimes de marché, stratégies par régime (trend, mean-reversion, breakout), sélection et combinaison |
| `references/indicators.md` | Indicateurs par famille, réglages, redondances à éviter, matrices de confluence |
| `references/chart-analysis.md` | Analyse multi-timeframe, structure de marché, supports/résistances, price action, patterns fiables |
| `references/risk-management.md` | Position sizing, levier, Kelly fractionné, stops/TP, kill-switch, checklist de veto |
| `references/ai-prompt.md` | Prompt système complet prêt à l'emploi pour l'IA qui gère les trades, format JSON, garde-fous |
| `references/backtesting.md` | Backtest honnête, pièges d'overfitting, walk-forward, métriques, protocole de mise en production |

## Anti-patterns à refuser explicitement

Si l'utilisateur demande l'un de ces éléments, expliquer pourquoi c'est destructeur et proposer l'alternative saine :

| Demande | Pourquoi c'est ruineux | Alternative |
|---------|------------------------|-------------|
| « Winrate 100 % » | Impossible ; pousse vers martingale/overfitting | Maximiser l'expectancy et le profit factor |
| Martingale / doubler après perte | Ruine certaine (une série de pertes suffit) | Risque fixe %, anti-martingale éventuel |
| Levier max (50–125×) | Liquidation sur bruit de marché normal | Levier dérivé du stop, effectif ≤ 5× |
| Supprimer le stop « pour laisser respirer » | Une perte non bornée efface des mois de gains | Stop structurel ATR + réduction de taille |
| Sur-optimiser sur l'historique | Courbe parfaite en backtest, pertes en réel | Walk-forward, paramètres robustes, out-of-sample |
| Trader toutes les paires/tous les signaux | Frais + corrélation cachée + bruit | 2–5 marchés maîtrisés, corrélation < 0,7 |
