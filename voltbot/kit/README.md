# ⚡ Kit VoltBot — indicateur + prompt + plan + stratégie

Le kit d'optimisation de [VoltBot](../README.md) (bot « trend hunter » haute volatilité,
Capital.com DÉMO). Quatre pièces, à utiliser dans cet ordre :

## 1. `indicateur/` — VoltScore (0-100)
L'indicateur personnalisé qui condense TOUTE la logique du bot en un score :
expansion de volatilité (25) + force de tendance (25) + cassure Donchian fraîche (25)
+ qualité momentum/exécution (25). Seuils : **≥ 70 = setup A+**, 55-69 = B, < 55 = rien.

- **`volt-score.pine`** → TradingView : ouvre l'éditeur Pine, colle le fichier,
  ajoute au graphique **M15** de GOLD/BTC/US30… Fond vert/rouge = direction,
  colonnes bleues = A+. Alertes intégrées (« VoltScore A+ BUY/SELL »).
  → Sert à VOIR ce que le bot voit, vérifier ses décisions, apprendre ses setups.
- **`volt-score.ts`** → même mathématique côté serveur, prête à brancher dans
  `volt-trader` (Palier 4 du plan : d'abord en shadow, ensuite en filtre si les
  données le justifient).

## 2. `prompt/` — le cerveau (Gemini v2)
- **`PROMPT-GEMINI.md`** : le prompt de décision déployé dans `volt-trader` v4,
  expliqué principe par principe — persona gestionnaire de risque, VoltScore
  injecté comme donnée objective avec droit de veto asymétrique, calibration
  ancrée par exemples, anti-injection, règles de modification. Le texte exact
  vit dans `supabase/functions/volt-trader/index.ts` (source de vérité).

## 3. `plan/` — la marche à suivre rigoureuse
- **`PLAN-AMELIORATION.md`** : 6 paliers (baseline → élagage des instruments →
  calibration LLM → réglage du trailing → VoltScore → montée en risque), avec les
  requêtes SQL prêtes à coller dans Supabase et les règles de décision chiffrées.
  **La règle d'or : un seul changement à la fois, échantillon suffisant.**
- **`JOURNAL-TEMPLATE.md`** : la revue du dimanche (10 min) — copie ce fichier
  chaque semaine et remplis-le. C'est la mémoire du système.

## 4. `strategie/` — mener tout ça au maximum
- **`STRATEGIE-MAX.md`** : les 5 étages (machine → discipline → optimisation →
  capital → écurie de bots), les critères non négociables de passage en réel,
  les pièges qui tuent les systèmes rentables, et ta routine.

---
*Généré le 2026-07-12 pour le projet VoltBot v3 (Supabase jarvis-mario, branche
`claude/trading-app-volatility-6xbgt1`).*
