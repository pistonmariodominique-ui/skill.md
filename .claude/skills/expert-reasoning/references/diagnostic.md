# Diagnostic & débogage — méthode hypothèses × preuves

Pour toute question du type « pourquoi ça ne marche pas / pourquoi ce résultat ? ».
Le but n'est pas de « tenter des trucs » mais de **faire converger l'espace des
causes possibles vers une seule, avec des preuves**.

## 1. D'abord : observer, pas supposer

- Reproduire ou constater le symptôme EXACT (message d'erreur complet, logs,
  données réelles). « Ça ne marche pas » n'est pas un symptôme.
- Établir la chronologie : quand est-ce que ça marchait ? Qu'est-ce qui a changé
  entre les deux ? (déploiement, réglage, données, heure, jour de la semaine).
- Vérifier l'état réel du système à la source (base de données, code DÉPLOYÉ —
  pas le dépôt qui peut être en retard, cf. l'écart v51 dépôt / v98 prod vécu
  sur le forexbot).

## 2. Générer les hypothèses (≥ 3 avant de creuser)

Pour chaque hypothèse, noter : ce qu'elle prédit d'observable, et le test le
moins cher qui la départage. Exemple vécu (« pas de trade depuis 3h30 ») :

| Hypothèse | Prédiction observable | Test |
|-----------|----------------------|------|
| Bot planté | Pas d'exécution des crons | Logs edge-function |
| Mode dégradé | consecutive_errors ≥ 3 | SELECT bot_status |
| Marché sans signal | Signaux HOLD avec raisons | SELECT signals récents |
| Quota atteint | trades du jour ≥ max | COUNT trades |

→ Un seul SELECT a tranché : signaux HOLD légitimes (RANGE), rien de cassé.

## 3. Bissecter

- Couper le chemin en deux : l'entrée est-elle bonne à mi-parcours ? (données →
  calcul → décision → exécution → notification). Tester au milieu, éliminer la
  moitié saine, recommencer.
- Dans le temps : dernier état sain connu vs premier état cassé → le coupable
  est dans l'intervalle (git log, historique des déploiements).

## 4. Conclure proprement

- Une cause est ÉTABLIE quand : (a) elle explique TOUTES les observations,
  (b) une preuve directe la confirme, (c) idéalement, la corriger fait
  disparaître le symptôme.
- Si deux causes coexistent (fréquent), les traiter séparément — une correction
  à la fois, sinon impossible d'attribuer l'effet.
- Écrire le diagnostic : symptôme → cause → preuve → correctif → comment éviter
  la récidive. (C'est ce qui alimente les handoffs et évite de re-payer.)

## 5. Pièges classiques

- **Corriger le symptôme, pas la cause** (relancer le bot sans comprendre les
  rejets → ils reviendront).
- **Le biais du dernier changement** : « c'est forcément ma modif d'hier » —
  parfois oui, mais le prouver (la modif peut être innocente et le vrai coupable
  être un changement externe : API tierce, données, horaire).
- **Deux numérotations / deux environnements** : toujours vérifier qu'on regarde
  la bonne version, le bon environnement, le bon fuseau horaire (UTC vs Paris a
  causé 2 bugs réels dans ce projet).
- **L'absence d'événement n'est pas une panne** : un système qui choisit de ne
  rien faire (HOLD) peut être en parfaite santé — vérifier ses raisons avant de
  le « réparer ».
