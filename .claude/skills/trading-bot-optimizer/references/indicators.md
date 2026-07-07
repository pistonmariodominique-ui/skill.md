# Indicateurs : sélection, réglages, confluence

## Principe : familles, pas quantité

Chaque indicateur appartient à une famille. **Deux indicateurs de la même famille = redondance**, pas confirmation. La confluence valide se construit avec **une seule voix par famille** :

| Famille | Rôle | Indicateurs | Choisir UN seul |
|---------|------|-------------|-----------------|
| Tendance | Direction & contexte | EMA 20/50/200, Supertrend, Ichimoku (nuage) | EMA multiples recommandé |
| Momentum | Force / essoufflement | RSI, Stochastique, MACD, CCI | RSI ou MACD |
| Volatilité | Régime & distances | ATR, Bollinger Bands, Keltner | ATR obligatoire (pour stops), Bollinger en option range |
| Volume | Conviction | Volume brut, OBV, Volume Profile (POC/VAH/VAL), CVD | Volume brut + profile si dispo |
| Structure | Niveaux | Swings HH/HL/LL/LH, S/R, order blocks, FVG | Toujours (voir chart-analysis.md) |

**Redondances classiques à supprimer lors d'un audit** : RSI + Stochastique + Williams %R (3× le même signal) ; MACD + croisements d'EMA (le MACD EST un croisement d'EMA) ; Bollinger + Keltner en double confirmation.

## Réglages de référence (point de départ, à valider en walk-forward)

- **EMA 20 / 50 / 200** — 20 : tendance courte et trailing ; 50 : zone de pullback ; 200 : biais directionnel (au-dessus = longs seulement, au-dessous = shorts seulement — filtre simple qui élimine énormément de mauvais trades).
- **RSI(14)** — en tendance : zones 40–50 (support haussier) / 50–60 (résistance baissière) pour les pullbacks ; en range : 30/70 pour les extrêmes. Divergences RSI/prix aux extrêmes = signal de retournement de qualité, surtout sur H4/D1.
- **MACD(12,26,9)** — croisements de la ligne de signal dans le sens de la tendance HTF uniquement ; l'histogramme qui décroît = momentum qui s'essouffle (utile pour prise de profit partielle).
- **ATR(14)** — jamais un signal d'entrée : c'est l'unité de mesure des stops (1–2×ATR), du filtre de volatilité (ATR vs moyenne) et du sizing.
- **ADX(14)** — filtre de régime : > 25 tendance, < 20 range (voir strategy.md).
- **Bollinger(20,2)** — squeeze = compression pré-breakout ; toucher de bande N'EST PAS un signal seul (en tendance, le prix « marche sur la bande »).
- **Volume** — un breakout sans volume > 1,5× la moyenne 20 est suspect ; une divergence prix ↑ / volume ↓ signale l'essoufflement.

## Matrice de confluence (exemple à adapter)

Une entrée LONG en régime de tendance haussière exige **toutes** les conditions A + au moins **2 des 3** conditions B :

**A — obligatoires (contexte)**
1. Prix > EMA200 H4 et structure HH/HL intacte (pas de CHoCH récent)
2. Pas de news à fort impact dans la fenêtre de blackout
3. R:R ≥ 1,5 vers la prochaine résistance/zone de liquidité

**B — confirmations (2/3 minimum)**
1. Momentum : RSI H1 rebondit depuis 40–50, ou croisement MACD haussier
2. Prix : rejet confirmé (mèche + clôture) d'une zone de demande / EMA50 / niveau S/R
3. Volume : pic de volume sur le rejet, ou POC du volume profile qui soutient la zone

Score de confluence = nombre de confirmations. Le score alimente le champ `confidence` du prompt IA (voir ai-prompt.md) et peut moduler la taille : score minimal → taille de base ; score maximal → jusqu'à 1,5× la taille de base (jamais plus, et toujours dans la limite du % de risque).

## Pièges

- **Plus d'indicateurs ≠ plus de précision.** Chaque indicateur ajouté augmente le risque d'overfitting et réduit le nombre de trades sans améliorer l'expectancy. 3–4 familles suffisent.
- **Les réglages « magiques » n'existent pas.** RSI(14) vs RSI(11) optimisé sur 6 mois d'historique : le second est presque toujours de l'overfitting. Préférer les réglages standards, robustes sur plusieurs marchés/périodes.
- **Tout indicateur est en retard.** Ils confirment la structure et le prix, ils ne les remplacent pas. La hiérarchie est : structure de marché > price action > indicateurs.
