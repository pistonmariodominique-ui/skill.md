# Front (Lovable) et gestion des clés

## 1. Les deux clés Supabase — règle absolue

| Clé | Où elle vit | Ce qu'elle peut faire |
|-----|-------------|------------------------|
| `anon` (publishable) | Dans le bundle JS du front = **PUBLIQUE** | Uniquement ce que les policies RLS autorisent aux rôles `anon`/`authenticated` |
| `service_role` | Env des edge functions **UNIQUEMENT** | TOUT, en ignorant le RLS |

- La `service_role` dans le front, dans un commit, dans un log ou un message =
  incident critique → rotation immédiate (Dashboard → Settings → API).
- La sécurité du front n'existe pas : tout ce que le JS « cache » (routes
  protégées, boutons masqués) est contournable. Seul le RLS + l'auth serveur
  comptent.

## 2. Audit côté front (code du dépôt, `src/`)

- [ ] Chercher toute clé/secret en dur : `grep -riE "(sk-|key|secret|token)\s*[:=]" src/` —
      seule l'anon key et l'URL du projet sont acceptables.
- [ ] Lister les tables consommées : `grep -rn "from('" src/` → base de
      l'inventaire « qui lit quoi » avant tout durcissement RLS.
- [ ] Les actions sensibles du dashboard (reset bot, toggle is_running) passent
      par : policy RLS restreinte à un utilisateur précis, OU une edge function
      authentifiée — jamais une policy `USING(true)`.
- [ ] Pas d'appel direct du front vers des API tierces avec des clés (Capital,
      Gemini…) : ces appels vivent dans les edge functions.

## 3. Auth de l'app

- Inscriptions : fermées ou sur allowlist tant que l'app est personnelle
  (Dashboard → Authentication → Sign In / Up).
- Si un seul utilisateur légitime : les policies d'écriture peuvent cibler son
  id : `USING (auth.uid() = '<uuid-de-mario>')` — simple et béton.
- Vérifier les redirect URLs OAuth (pas de wildcard), et la durée des sessions.

## 4. Divers

- CORS des edge functions : si la fonction n'est appelée que par le cron, aucun
  en-tête CORS n'est nécessaire (ne pas ajouter `Access-Control-Allow-Origin: *`
  par réflexe).
- Dépendances front : `bun audit` / vérifier les CVE lors des mises à jour
  Lovable ; ne pas introduire de scripts tiers non nécessaires.
- Le dépôt GitHub : jamais de `.env` committé (vérifier `.gitignore`), et
  activer le secret scanning GitHub si disponible.
