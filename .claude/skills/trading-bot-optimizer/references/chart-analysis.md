# Analyse graphique : multi-timeframe, structure, price action

## 1. Multi-timeframe (MTF) — la règle des 3 écrans

Toujours analyser 3 timeframes avec un ratio de 4–6× entre chacun :

| Rôle | Exemple intraday | Exemple swing | Question |
|------|------------------|---------------|----------|
| **Contexte (HTF)** | H4 | D1/W1 | Quelle est la tendance ? Où sont les grandes zones ? |
| **Setup (MTF)** | H1 | H4 | Le prix arrive-t-il sur une zone d'intérêt avec un setup ? |
| **Déclencheur (LTF)** | M15 | H1 | Confirmation d'entrée précise (rejet, break de micro-structure) |

Règle absolue : **on ne trade que dans le sens du contexte HTF** (ou pas du tout). Le LTF sert uniquement à affiner l'entrée et à réduire la distance du stop — jamais à contredire le HTF.

## 2. Structure de marché (à coder / à faire lire à l'IA)

- **Tendance haussière** : suite de Higher Highs (HH) et Higher Lows (HL).
- **Tendance baissière** : Lower Lows (LL) et Lower Highs (LH).
- **BOS (Break of Structure)** : cassure dans le sens de la tendance → continuation.
- **CHoCH (Change of Character)** : première cassure contre-tendance (ex. : un HL cassé en tendance haussière) → alerte de retournement ; on ne shorte pas le CHoCH lui-même, on attend la confirmation (LH puis LL).
- Les swings se détectent objectivement : pivot = plus haut/bas local sur N bougies de chaque côté (N=2–3 LTF, N=5 HTF). L'implémentation doit être déterministe pour être backtestable.

## 3. Niveaux : supports, résistances, zones

- Tracer des **zones**, pas des lignes (épaisseur ≈ 0,25–0,5×ATR).
- Un niveau vaut par : nombre de touches (2–3 = fort ; 5+ = fragilisé), réaction passée (violence du rejet), confluence (niveau + EMA200 + POC volume = zone majeure), fraîcheur (une zone jamais retestée est plus fiable).
- **Rôle inversé** : une résistance cassée proprement devient support (et inversement) — le retest de polarité est l'un des setups les plus fiables.
- Zones de liquidité : sous les swing lows évidents / au-dessus des swing highs s'accumulent les stops. Les mèches de chasse aux stops (sweep) suivies d'un retour rapide = signal de retournement exploitable ; à l'inverse, placer ses propres stops AU-DELÀ de ces poches, pas dedans.

## 4. Price action : les signaux qui comptent

Hiérarchie de fiabilité (sur une zone d'intérêt uniquement — un pattern « au milieu de nulle part » ne vaut rien) :

1. **Sweep + reclaim** : mèche qui prend la liquidité sous un niveau puis clôture au-dessus.
2. **Engulfing** (avalement) avec clôture au-delà du corps précédent, sur volume.
3. **Pin bar / marteau** : mèche ≥ 2× le corps, rejetant la zone.
4. **Inside bar** en compression sur un niveau → trade du break.

Toujours attendre la **clôture** de la bougie de signal. Entrer sur une bougie en cours = signal non confirmé (repaint) et cause majeure de faux backtests.

## 5. Patterns graphiques : sobriété

- Fiables et objectivables : range (rectangle), triangle de compression, double top/bottom AVEC divergence momentum, pullback en drapeau dans une tendance.
- À ignorer pour un bot : figures subjectives (épaule-tête-épaule mal définie, harmoniques exotiques, biseaux ambigus) — trop dépendantes de l'œil humain, non reproductibles en backtest.

## 6. Checklist d'analyse avant chaque trade (à intégrer au prompt IA)

1. Tendance HTF (structure + EMA200) : haussière / baissière / neutre ?
2. Régime (ADX/ATR) : trend / range / compression / chaos ?
3. Où sont les 2 zones majeures les plus proches (au-dessus / au-dessous) ?
4. Le prix est-il SUR une zone d'intérêt, ou entre deux zones (no-trade) ?
5. Y a-t-il un signal price action confirmé en clôture sur cette zone ?
6. La confluence indicateurs valide-t-elle (voir indicators.md) ?
7. Le stop structurel donne-t-il un R:R ≥ 1,5 vers la prochaine zone ?
8. Session/news : le moment est-il tradable ?

Si une réponse est douteuse → pas de trade. L'absence de trade a une valeur positive : chaque mauvais trade évité améliore l'expectancy autant qu'un gagnant.
