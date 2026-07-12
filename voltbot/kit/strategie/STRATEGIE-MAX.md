# 🎯 Stratégie MAX — mener VoltBot au maximum de son potentiel

> La philosophie qu'on a figée ensemble :
> **« Maximise la volatilité dans le CHOIX des instruments. Minimise la FRÉQUENCE des trades.
> Coupe vite les perdants, laisse courir les gagnants très loin. »**
> Ce document est la feuille de route pour transformer ça en résultats durables.

---

## Étage 1 — La machine (fait ✅)

VoltBot v3 : 7 instruments volatils, crypto 24/7, thèse M15 + entrée M5, SL serré,
breakeven +1×SL, trailing 2.5×ATR, stop garanti anti-gap, filtres vol/spread/news,
fusibles jour/semaine. **Ta seule mission ici : le laisser travailler.**

## Étage 2 — La discipline (le vrai multiplicateur)

90 % des systèmes rentables meurent de la main de leur propriétaire. Les trois
comportements qui font TOUTE la différence :

1. **Respecter le PLAN-AMELIORATION à la lettre** — un changement à la fois,
   échantillon suffisant, journal hebdo. C'est ennuyeux. C'est le but.
2. **Accepter les séries de pertes.** Trend hunter à 40 % de winrate = des séries
   de 5-7 pertes consécutives sont STATISTIQUEMENT NORMALES (ça arrivera ~1 fois
   par mois). Le gagnant à +6×ATR qui paie tout arrive précisément après.
3. **Ne jamais « aider » le bot** : pas de fermeture manuelle d'un trade en profit
   (c'est le trailing qui décide), pas de trade manuel sur le même compte
   (ça fausse la réconciliation ET les stats).

## Étage 3 — L'optimisation guidée par les données (mois 1-3)

Suis les paliers du PLAN. Les deux leviers qui rapporteront le plus, dans l'ordre :

1. **L'élagage des instruments** (Palier 1). Sur 7 instruments, il y en aura
   probablement 2-3 vraiment rentables. Concentrer le capital dessus est le gain
   le plus facile de toute l'aventure.
2. **Le réglage du trailing** (Palier 3). C'est le paramètre le plus sensible d'un
   trend follower : trop serré = on coupe les tsunamis, trop lâche = on rend tout.
   Les données `max_pnl_points / atr_at_open` te diront où est l'argent laissé
   sur la table.

Le VoltScore (Palier 4) vient APRÈS : c'est un raffinement, pas une fondation.

## Étage 4 — La montée en capital (mois 3-6)

**Sur le DÉMO d'abord** : risque 0.5 % → 0.75 % → 1.0 % selon les critères du
Palier 5 (profit factor > 1.3, drawdown < 10 %). La croissance vient de
l'expectancy × la fréquence × le risque — dans CET ordre de priorité.

**Critères de passage en RÉEL (tous obligatoires)** :
- ≥ 3 mois de démo ET ≥ 100 trades propres réconciliés
- Profit factor global > 1.3 · expectancy > 0 · drawdown max < 15 %
- Au moins 2 mois positifs sur 3
- Tu as vécu une série de ≥ 5 pertes SANS toucher aux réglages (test psychologique réel)

**Le jour du passage en réel** :
- Capital de départ : une somme dont la perte TOTALE ne change rien à ta vie.
- `risk_pct` redescend à 0.5 % (le slippage et l'exécution réelle sont différents du démo).
- `sizing_capital_cap` = ton capital réel si le compte en contient plus.
- Les 2 premiers mois en réel = re-validation, pas expansion.

## Étage 5 — L'écurie de bots (mois 6+)

Le plafond d'UN bot est vite atteint ; la suite c'est le **portefeuille de stratégies** :
- **ForexBot** (retour à la moyenne, paires calmes) + **VoltBot** (tendance, instruments
  violents) sont déjà complémentaires : leurs profits arrivent dans des régimes de
  marché opposés → la courbe combinée est plus lisse que chacune.
- 3ᵉ candidat naturel plus tard : un bot de **breakout hebdomadaire** (H4/D1, 1-2
  trades/mois, cibles 10×ATR) — même code, autre échelle de temps.
- À ce stade : un compte (démo puis réel) PAR bot pour isoler capital et statistiques
  — la limite du montage actuel (compte partagé) se règle là.

## Les tueurs de performance (à afficher au mur)

| Piège | Antidote |
|---|---|
| Bidouiller après 3 pertes | Fusibles jour/semaine + journal + paliers |
| Couper le bot en drawdown | Décision UNIQUEMENT le dimanche, jamais en séance |
| Sur-optimiser (courbe parfaite sur le passé) | Un paramètre à la fois, jamais > 1 test/2 semaines |
| Ajouter des instruments « pour plus d'action » | Un instrument se mérite (Palier 1 à l'envers) |
| Passer en réel trop tôt | Les 4 critères de l'Étage 4, non négociables |
| Winrate-mania | L'expectancy est la seule boussole |

## Ta routine (le contrat)

- **Chaque jour (2 min)** : lire les messages Telegram. Ne RIEN faire d'autre.
- **Chaque dimanche (15 min)** : requêtes SQL → JOURNAL-TEMPLATE → une décision max.
- **Chaque mois (30 min)** : relire ce document + le PLAN, vérifier le palier en cours,
  archiver le journal.

C'est tout. La machine chasse, les données décident, toi tu pilotes la discipline.
