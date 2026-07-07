# Gestion du risque : sizing, levier, stops, kill-switch

C'est la couche qui détermine la survie. Un edge moyen + un excellent risk management = compte qui croît. Un excellent edge + un mauvais risk management = ruine (question de temps).

## 1. Position sizing — LA formule

Le risque par trade est fixe : **R = 0,5 à 2 % du capital** (1 % par défaut ; 0,5 % en phase de validation ; 2 % maximum absolu pour un système prouvé sur 200+ trades réels).

```
risque_€        = capital × R                    (ex. 10 000 € × 1 % = 100 €)
distance_stop   = |prix_entrée − prix_stop|       (déterminée par la STRUCTURE, jamais par le levier)
taille_position = risque_€ / distance_stop        (en unités de l'actif)
valeur_position = taille_position × prix_entrée
levier_requis   = valeur_position / capital_alloué_au_trade
```

**Ordre du raisonnement : structure → stop → taille → levier.** Quiconque choisit d'abord le levier puis place le stop « où ça passe » a inversé la logique et perdra.

## 2. Effet de levier

- Le levier n'augmente pas l'espérance de gain ; il augmente la vitesse (dans les deux sens) et ajoute des coûts (funding) et un risque de liquidation.
- **Levier effectif** (valeur totale des positions / capital) à surveiller, pas le levier affiché par l'exchange :
  - Crypto : ≤ 3× prudent, ≤ 5× maximum. Au-delà, une mèche de volatilité normale (2–3×ATR) peut liquider une position pourtant « juste ».
  - Forex majors : ≤ 10×. Indices : ≤ 5×.
- **Prix de liquidation toujours ≥ 2× plus loin que le stop-loss.** Si la liquidation est plus proche que 2× la distance du stop, réduire le levier. Le stop doit toujours se déclencher bien avant la liquidation.
- Funding/overnight : en crypto perp, un funding de 0,01 %/8 h ≈ 11 %/an sur la valeur notionnelle — à intégrer au backtest pour les positions > 24 h.

## 3. Kelly fractionné (pour calibrer R, pas pour le remplacer)

```
kelly = W − (1 − W) / RR        (W = winrate, RR = gain moyen / perte moyenne)
```

Exemple : W = 50 %, RR = 2 → kelly = 25 %. **Ne JAMAIS trader le Kelly plein** (variance insoutenable, estimation de W/RR toujours incertaine). Utiliser **Kelly/4 à Kelly/10**, plafonné à 2 %. Si le Kelly calculé est ≤ 0, le système n'a pas d'edge : ne pas trader, retourner en backtest.

## 4. Stops et take-profits

- **Stop initial** : au-delà de l'invalidation structurelle (swing/zone) ± 1×ATR(14) de marge anti-mèche. Un stop « serré pour augmenter la taille » qui ne correspond à aucune invalidation = stop chassé en boucle.
- **Jamais élargir un stop.** Jamais. C'est la règle la plus violée et la plus coûteuse.
- **Break-even** : déplacer le stop à l'entrée (+ frais) quand le trade atteint +1R. Réduit la variance, coût minime en expectancy.
- **TP hybride recommandé** : 50 % de la position à +1,5R (sécurise, finance le risque), le reste en trailing (EMA20, dernier swing, ou 2×ATR chandelier) pour capturer les grandes tendances. C'est le meilleur compromis winrate/expectancy pour la plupart des bots.
- **Time-stop** : si le trade n'a atteint ni +1R ni le stop après N bougies (ex. 24 h en H1), sortir — le capital immobilisé sans thèse active est un coût d'opportunité.

## 5. Kill-switch et limites globales (à coder EN DUR, hors du prompt IA)

| Limite | Seuil | Action |
|--------|-------|--------|
| Perte journalière | −3 % du capital | Bot en pause 24 h |
| Perte hebdomadaire | −6 % | Pause 7 jours + revue du journal |
| Drawdown total | −10 % depuis le plus haut | Arrêt complet, audit obligatoire avant redémarrage |
| Pertes consécutives | 4 trades | Taille divisée par 2 jusqu'à 2 gagnants |
| Positions simultanées | 3 max (corrélation < 0,7 entre elles) | Rejeter les nouveaux signaux |
| Risque total ouvert | ≤ 4 % du capital | Rejeter ou réduire |
| Erreur technique (API, données) | Toute anomalie | Fermer les positions gérées, alerter, stopper |

Ces limites vivent dans le code d'exécution, **pas** dans le prompt de l'IA : une IA peut halluciner ou être manipulée par le contexte, le code non.

## 6. Filtres de veto (couche 4 du pipeline)

Rejeter tout signal si :
- News à fort impact dans [−15 min, +30 min] (calendrier économique ; pour crypto : FOMC, CPI, décisions SEC/ETF).
- Spread > 1,5× le spread médian (liquidité dégradée).
- Position déjà ouverte corrélée > 0,7 (BTC et ETH = quasi la même position).
- Session morte pour l'instrument (ex. : forex hors Londres/NY ; volumes crypto minimaux 2 h–6 h UTC).
- Week-end pour les gaps forex ; funding extrême (> 0,1 %/8 h) en crypto perp = surchauffe.
- Le kill-switch est actif ou la limite de positions est atteinte.

## 7. Ce qui est interdit, toujours

- Martingale, grid sans stop global, moyenne à la baisse sur position perdante.
- Position sans stop, stop « mental », stop déplacé contre soi.
- Augmenter la taille pour « se refaire » après une perte (revenge trading algorithmisé).
- Risquer sur un trade plus que le plafond, quel que soit le « niveau de confiance ».
- Compter sur le prix de liquidation comme stop-loss.
