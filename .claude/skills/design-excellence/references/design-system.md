# Design system — tokens prêts à copier

Point de départ neutre et solide. À adapter au ton du projet (étape 1), jamais
à ignorer. Format : variables CSS ; transposer en config Tailwind si besoin.

## 1. Espacement (échelle unique — TOUTES les marges/paddings viennent d'ici)

```css
--space-1: 4px;  --space-2: 8px;  --space-3: 12px; --space-4: 16px;
--space-5: 24px; --space-6: 32px; --space-7: 48px; --space-8: 64px;
--space-9: 96px; /* sections de landing */
```
Usage type : padding interne des cartes 16–24 ; écart entre éléments liés 8–12 ;
entre groupes 24–32 ; entre sections 64–96. Mobile : réduire d'un cran.

## 2. Typographie

```css
--font-heading: 'Inter', system-ui, sans-serif;   /* ou une serif éditoriale */
--font-body:    'Inter', system-ui, sans-serif;
--text-xs: 12px; --text-sm: 14px; --text-base: 16px; --text-lg: 20px;
--text-xl: 25px; --text-2xl: 31px; --text-3xl: 39px; --text-4xl: 49px;
```
- Corps de texte : 16px minimum (14 acceptable en dashboard dense), line-height 1,5.
- Titres : line-height 1,1–1,2, letter-spacing léger négatif (-0.01em à -0.02em)
  au-delà de 31px.
- Largeur de lecture : 60–75 caractères max (`max-width: 65ch`).
- Chiffres alignés dans les tableaux : `font-variant-numeric: tabular-nums`.
- Hiérarchie sans multiplier les tailles : jouer poids (400/500/600/700) et
  couleur (texte principal vs secondaire) avant d'ajouter une taille.

## 3. Couleur — structure 60-30-10

Mode clair :
```css
--bg: #FAFAF9;            /* fond, 60% — blanc cassé teinté, jamais #FFF pur plein écran */
--surface: #FFFFFF;       /* cartes, 30% */
--border: #E7E5E4;
--text: #1C1917;          /* quasi-noir teinté, jamais #000 */
--text-muted: #78716C;    /* contraste ≥ 4,5:1 sur --surface : vérifier ! */
--accent: #4F46E5;        /* 10% — UN seul accent */
--accent-hover: #4338CA;
--success: #16A34A; --danger: #DC2626; --warning: #D97706;
```
Mode sombre (pas une simple inversion) :
```css
--bg: #0C0A09;            /* sombre teinté, jamais #000 */
--surface: #1C1917;       /* surfaces PLUS CLAIRES que le fond (élévation) */
--border: #292524;
--text: #FAFAF9;          /* jamais #FFF pur : #F5F5F4 max */
--text-muted: #A8A29E;
--accent: #818CF8;        /* accent ÉCLAIRCI en dark (le clair vibre trop) */
--success: #4ADE80; --danger: #F87171; --warning: #FBBF24;
```
Règles :
- Sémantique stable : vert = gain/succès, rouge = perte/erreur — jamais détournés.
- L'accent sert aux ACTIONS et à l'info clé, pas à la décoration.
- Dégradés : 2 teintes voisines max, réservés aux heros/CTA.
- Vérifier chaque paire texte/fond ≥ 4,5:1 (grands titres ≥ 3:1) — outil, pas à l'œil.

## 4. Rayons, ombres, élévation

```css
--radius-sm: 6px; --radius-md: 10px; --radius-lg: 16px; --radius-full: 9999px;
--shadow-sm: 0 1px 2px rgb(0 0 0 / 0.05);
--shadow-md: 0 4px 12px rgb(0 0 0 / 0.08);
--shadow-lg: 0 12px 32px rgb(0 0 0 / 0.12);
```
- Une seule « source de lumière » : ombres toujours vers le bas.
- En dark mode, l'élévation passe par la CLARTÉ de surface plus que par l'ombre.
- Glassmorphism (si direction choisie) : `backdrop-filter: blur(12px)` + fond
  `rgb(255 255 255 / 0.06)` + bordure `rgb(255 255 255 / 0.12)` — sur 1-2
  surfaces stratégiques, texte à contraste vérifié par-dessus.

## 5. Breakpoints & responsive

```css
/* mobile-first : base = 320-390px */
--bp-sm: 640px; --bp-md: 768px; --bp-lg: 1024px; --bp-xl: 1280px;
```
- Cibles tactiles ≥ 44×44px, espacées ≥ 8px.
- Grilles : 4 colonnes mobile, 8 tablette, 12 desktop ; conteneur max 1200–1280px.
- Tableaux en mobile : scroll horizontal contenu dans la carte OU transformation
  en cartes — jamais de page qui scrolle latéralement.
- Tester 320px (petit Android) ET 1440px : les deux cassent des layouts différents.

## 6. Dashboards & données (cas fréquent des projets du proprio)

- KPI en tuiles : chiffre énorme (--text-2xl+, tabular-nums), label discret
  au-dessus, variation colorée (▲ vert / ▼ rouge) avec signe + valeur.
- Densité : viser ~8-12 infos par écran mobile, aérées ; le scan vertical prime.
- États temps réel : timestamp de dernière mise à jour TOUJOURS visible
  (un dashboard sans « à jour il y a 2 min » ment par omission).
- Graphiques : 1 couleur par série liée aux tokens, grilles très discrètes,
  pas de 3D, pas de camembert au-delà de 4 parts.
