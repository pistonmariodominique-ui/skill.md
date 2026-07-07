# Revue finale de design — checklist avant livraison

À dérouler sur CHAQUE écran avant de dire « fini ». Un point non coché = pas fini.

## 1. Les 10 fautes d'amateur (traquer en premier)

1. Marges hors échelle (13px, 22px, 37px…) → tout ramener aux tokens.
2. Deux éléments « presque alignés » ou « presque de la même taille » → aligner
   exactement ou différencier franchement. Le presque-pareil est pire que le différent.
3. Texte gris trop clair (contraste < 4,5:1) → assombrir, mesurer.
4. Plus d'un élément qui réclame l'attention en premier → rétrograder les autres.
5. #000 pur, #FFF pur, gris neutres purs → teinter légèrement.
6. Icônes de tailles/styles mélangés (outline + filled) → un seul set, une grille (20/24px).
7. Boutons primaires multiples sur le même écran → UN primaire, le reste en
   secondaire/ghost.
8. Placeholder utilisé comme label de formulaire → label visible permanent.
9. Ombres incohérentes (directions/intensités variées) → un seul système.
10. Composants sans états vide/chargement/erreur → les concevoir, avec un
    message utile et une action (« Aucun trade aujourd'hui — le bot analyse
    toutes les 15 min »).

## 2. Accessibilité (non négociable, 10 minutes)

- [ ] Contraste : texte normal ≥ 4,5:1, grands titres ≥ 3:1, éléments UI ≥ 3:1.
- [ ] Navigation clavier complète : tab dans l'ordre visuel, focus VISIBLE
      (outline/ring, jamais `outline: none` sans remplacement).
- [ ] L'information n'est jamais portée par la couleur SEULE (gain/perte : signe
      +/− ou icône en plus du vert/rouge — daltonisme).
- [ ] Alt text sur les images porteuses de sens ; `aria-label` sur les boutons icône.
- [ ] Zoom 200 % : rien ne casse, rien ne disparaît.
- [ ] `prefers-reduced-motion` respecté si animations.

## 3. Responsive

- [ ] 320px : pas de scroll horizontal, cibles tactiles ≥ 44px, textes lisibles.
- [ ] 768px : le layout se réorganise (pas juste rétréci).
- [ ] 1440px : le contenu ne s'étale pas à l'infini (conteneur max, lignes ≤ 75ch).
- [ ] Images : `max-width: 100%`, dimensions réservées (pas de saut de layout).

## 4. Cohérence système

- [ ] Zéro valeur magique : tout espacement/couleur/taille vient des tokens.
- [ ] Un composant qui se répète a EXACTEMENT le même style partout.
- [ ] Dark mode (si présent) : testé réellement, y compris images/logos et états.
- [ ] Vocabulaire des actions constant (« Enregistrer » partout, pas « Sauver »
      ici et « Valider » là).

## 5. Perception de qualité (les 5 derniers %)

- [ ] Hiérarchie : plisser les yeux devant l'écran — l'élément le plus visible
      est-il le plus important ? Le regard suit-il l'ordre voulu ?
- [ ] Micro-détails : curseurs corrects (pointer sur cliquable), transitions sur
      hover, sélection de texte stylée, favicon, titres d'onglet propres.
- [ ] Vitesse ressentie : squelettes/spinners au-delà de 300 ms d'attente,
      optimistic UI sur les actions simples.
- [ ] Contenu réel testé : textes longs, nombres larges (999 999,99 €), noms à
      rallonge — rien ne déborde ni ne casse.
- [ ] Comparer à la référence choisie à l'étape 1 : même niveau de retenue ?
      (Si la référence a 1 accent et 3 tailles de texte, l'écran aussi.)

## 6. Verdict

Rendu final jugé sur 3 questions :
1. En 3 secondes, comprend-on où on est et quoi faire ? (hiérarchie)
2. Y a-t-il UN détail incohérent qui trahit l'amateurisme ? (système)
3. Est-ce fidèle aux 3 adjectifs du cadrage ? (direction)
Trois oui = livrable. Sinon, corriger le point précis — pas tout redessiner.
