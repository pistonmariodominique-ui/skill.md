# Stratégies par régime de marché

La cause n° 1 de non-rentabilité d'un bot : appliquer une stratégie dans le mauvais régime. La détection du régime est donc la **première étape** de chaque cycle de décision.

## 1. Détection du régime de marché

Calculer sur le timeframe de contexte (H4 ou D1 pour un bot intraday) :

| Régime | Détection | ADX(14) | Autres signaux |
|--------|-----------|---------|----------------|
| **Tendance haussière** | HH/HL en structure, prix > EMA200, EMA50 > EMA200 | > 25 | Pente EMA200 positive |
| **Tendance baissière** | LL/LH, prix < EMA200, EMA50 < EMA200 | > 25 | Pente EMA200 négative |
| **Range** | Pas de structure directionnelle, prix oscille entre 2 niveaux | < 20 | Bollinger plates, ATR stable |
| **Haute volatilité / chaos** | ATR > 1,5× sa moyenne 20 périodes, mèches larges | variable | Souvent autour de news |
| **Compression (pré-breakout)** | Bollinger squeeze, ATR décroissant, range étroit | < 20 | Volume décroissant |

Règle : **ADX entre 20 et 25 = zone grise → pas de trade** (ou taille réduite de moitié).

## 2. Stratégie par régime

### Tendance → Trend-following / Pullback
- **Entrée** : pullback sur EMA20/50 ou sur zone de demande (order block), confirmation par reprise du momentum (RSI qui rebondit sur 40–50 en tendance haussière, engulfing, break de micro-structure LTF).
- **Ne jamais** entrer en chasse après une bougie d'extension (attendre le retracement).
- **Stop** : sous le dernier swing low (long) ± 1×ATR(14).
- **TP** : trailing sur EMA20/structure, ou TP partiel à 1,5R puis laisser courir.
- Winrate attendu : 40–55 %, R:R moyen 1:2 à 1:4. La rentabilité vient des gros gagnants : **ne pas couper les gains trop tôt.**

### Range → Mean-reversion
- **Entrée** : rejet confirmé des bornes du range (mèche + clôture retour dans le range), RSI > 70 / < 30, écart aux Bollinger.
- **Interdit** : mean-reversion quand ADX > 25 (c'est un breakout qui commence, pas un excès).
- **Stop** : au-delà de la borne + 1×ATR (un vrai breakout doit invalider vite).
- **TP** : milieu du range (conservateur) ou borne opposée (agressif, TP partiel au milieu).
- Winrate attendu : 60–70 %, R:R 1:1 à 1:1,5. Les pertes viennent des breakouts : le stop doit être respecté à la lettre.

### Compression → Breakout
- **Entrée** : clôture au-delà du range sur volume > 1,5× moyenne, idéalement retest de la borne cassée.
- **Filtre anti-faux-breakout** : attendre la clôture de la bougie (jamais entrer sur la mèche), exiger le volume, éviter les breakouts pendant les sessions creuses (nuit US pour crypto, vendredi soir forex).
- **Stop** : de l'autre côté de la zone de compression.
- Winrate attendu : 35–45 %, R:R 1:2,5+. Beaucoup de faux signaux, gros gagnants rares mais décisifs.

### Haute volatilité / news → NE PAS TRADER
- Blackout automatique : 15 min avant → 30 min après toute news à fort impact (FOMC, CPI, NFP, décisions de taux, halving/ETF pour crypto).
- Si ATR > 2× sa moyenne : réduire le risque par trade de moitié ou couper le bot.

## 3. Combinaison des stratégies

- Un bot robuste = 2–3 stratégies **décorrélées** (ex. : pullback de tendance H1 + mean-reversion range H1 + breakout D1), chacune activée par son régime, avec un budget de risque commun.
- Suivre l'expectancy **par stratégie et par régime** dans le journal. Toute stratégie dont l'expectancy sur 50+ trades est négative est désactivée, pas « ajustée » à chaud.
- Ne jamais laisser deux stratégies ouvrir des positions corrélées simultanément (voir risk-management, corrélation).

## 4. Sélection des marchés

- 2 à 5 instruments liquides maximum (spread faible, profondeur), corrélation croisée < 0,7.
- Crypto : privilégier BTC/ETH + 1–2 majors ; éviter les small caps (manipulation, spreads).
- Forex : majors (EURUSD, GBPUSD, USDJPY) ; éviter les exotiques.
- Vérifier les frais : un scalping M1 rentable à 0 frais est presque toujours perdant avec frais + slippage réels. Timeframes M15+ recommandés pour un bot retail.
