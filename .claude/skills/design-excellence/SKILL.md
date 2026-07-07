---
name: design-excellence
description: "Méthode de design universelle pour tout projet futur : landing page, dashboard, app mobile, SaaS, e-commerce, portfolio. Processus complet — direction artistique, système de design (espacements, typographie, couleurs, tokens), hiérarchie visuelle, composants, états, animation, accessibilité, revue finale. Actions : designer, créer, améliorer, refondre, styliser, moderniser une interface, choisir des couleurs/polices, rendre pro/premium/élégant. Sujets : UI, UX, design system, palette, typographie, espacement, contraste, dark mode, responsive, glassmorphism, minimalisme, accessibilité, hiérarchie. Utiliser ce skill dès qu'on crée ou améliore une interface ; se combine avec ui-ux-pro-max (données) si présent."
---

# Design Excellence — méthode pour des interfaces pro, quel que soit le projet

Ce skill apporte la **méthode et les règles de décision**. Si le skill `ui-ux-pro-max` est disponible dans le projet, l'utiliser comme **base de données** (styles, palettes, paires de polices, guidelines par stack) — les deux se complètent : méthode ici, catalogue là-bas.

## ⚠️ Principe fondateur

**Le design amateur vient de l'incohérence, pas du manque de talent.** 90 % du rendu « pro » s'obtient mécaniquement : un système d'espacement respecté partout, UNE échelle typographique, UNE palette restreinte appliquée avec logique, et une hiérarchie visuelle qui dit à l'œil où regarder en premier. D'abord le système, ensuite la créativité.

## Processus en 6 étapes (jamais sauter la 1 et la 2)

### 1. Cadrer avant de dessiner
- **Qui** utilise, sur **quel appareil**, pour **faire quoi en priorité** ? L'action n°1 de l'écran doit être décidée AVANT tout pixel (un dashboard de bot de trading = lire l'état en 3 secondes ; une landing = un seul CTA).
- **Ton émotionnel** en 3 adjectifs (ex. : « premium, sobre, technique » ≠ « chaleureux, ludique, accessible ») — chaque choix ultérieur se juge contre ces 3 mots.
- Type de projet → priorités différentes : landing (conversion, vitesse), dashboard (densité lisible, scan), app mobile (pouce, tactile ≥ 44px), e-commerce (confiance, images).

### 2. Poser le système AVANT les écrans (`references/design-system.md`)
- **Espacement** : échelle unique 4/8px (4, 8, 12, 16, 24, 32, 48, 64…). Toute marge hors échelle est un bug.
- **Typographie** : 2 polices max (titre + texte), échelle modulaire (ex. 12/14/16/20/25/31/39), line-height 1,5 pour le texte, 1,1–1,2 pour les titres.
- **Couleurs** : règle 60-30-10 (fond / surfaces / accent). 1 accent, pas 4. Neutres teintés (jamais de gris purs #808080). Contraste ≥ 4,5:1 texte normal.
- **Rayons, ombres, bordures** : 2-3 valeurs de rayon max, ombres cohérentes (même direction de lumière partout).
- Tout écrire en **tokens** (variables CSS/Tailwind config) — jamais de valeurs magiques dans les composants.

### 3. Hiérarchie visuelle (ce qui sépare pro et amateur)
- Chaque écran a UN élément dominant. Si tout crie, rien ne s'entend.
- Outils de hiérarchie, dans l'ordre de puissance : taille → contraste/couleur → poids → espace autour → position. En utiliser 2 par niveau, pas 5.
- **L'espace blanc est un matériau**, pas du vide : grouper par proximité (ce qui va ensemble est proche), séparer les sections par l'espace avant d'ajouter des bordures.
- Alignement : tout élément est aligné sur quelque chose (grille 12 colonnes web, gouttières constantes). Un seul axe d'alignement fort par zone.

### 4. Composants et états (là où les projets « presque finis » échouent)
Chaque composant interactif a TOUS ses états : défaut, hover, focus (visible !), actif, désactivé, chargement, erreur, vide. Un tableau sans état vide (« aucun trade aujourd'hui ») ou un bouton sans état loading = design incomplet.
- Formulaires : label toujours visible (pas placeholder seul), erreur à côté du champ, bouton désactivé jamais sans explication.
- Feedback : toute action utilisateur reçoit une réponse < 100 ms (même juste visuelle).

### 5. Mouvement et micro-interactions
- Transitions 150–250 ms, easing `ease-out` pour entrer, `ease-in` pour sortir. Jamais > 400 ms sur de l'utilitaire.
- Animer 2 propriétés max à la fois (opacity + transform de préférence — performantes).
- Le mouvement a un SENS (guider l'attention, montrer la provenance) — pas de décoration gratuite. Respecter `prefers-reduced-motion`.

### 6. Revue finale (`references/review-checklist.md`)
Passer la checklist AVANT de livrer : contraste, responsive 320px→1440px, dark mode, clavier, cohérence des tokens, plus les 10 fautes d'amateur à traquer.

## Directions esthétiques éprouvées (choisir UNE, s'y tenir)

| Direction | Quand | Signature |
|-----------|-------|-----------|
| Minimalisme premium | SaaS, finance, portfolio haut de gamme | Beaucoup d'espace, 1 accent, typographie soignée, ombres subtiles |
| Dark mode technique | Dashboards, outils dev/trading | Fonds #0B–#15 teintés, accents néon dosés, données en évidence |
| Glassmorphism dosé | Landing moderne, hero sections | Flou + transparence sur 1-2 surfaces MAX, jamais partout |
| Éditorial | Contenu, blogs, marques | Grosse typo serif, grilles asymétriques, images fortes |
| Brutalisme soft | Marques jeunes, créatifs | Bordures franches, couleurs vives, ombres dures — cohérence stricte requise |

Règle : le style se choisit à l'étape 1 (ton émotionnel), s'implémente via les tokens de l'étape 2, et ne se mélange pas à un autre en cours de route.

## Anti-patterns à refuser

| Demande / réflexe | Pourquoi c'est mauvais | Alternative |
|-------------------|------------------------|-------------|
| « Ajoute plus de couleurs/effets pour faire pro » | Le pro = retenue + cohérence | Renforcer hiérarchie et espacements |
| Centrer tout le texte | Illisible au-delà de 2 lignes | Aligné à gauche, centré réservé aux heros |
| 5 polices, 4 accents, 3 styles | Incohérence = amateur | 2 polices, 1 accent, 1 direction |
| Texte gris clair sur blanc « élégant » | Contraste < 4,5:1 = illisible + inaccessible | Neutres foncés teintés |
| Tout en modales et carrousels | Patterns à friction, cachent le contenu | Contenu à plat, pages dédiées |
| Copier 3 sites différents | Frankenstein visuel | 1 référence principale, adaptée au système |

## Fichiers de référence

| Fichier | Contenu |
|---------|---------|
| `references/design-system.md` | Tokens concrets prêts à copier : échelles, palettes types (clair/sombre), typo, ombres, breakpoints |
| `references/review-checklist.md` | Checklist de revue finale + les 10 fautes d'amateur + accessibilité |
