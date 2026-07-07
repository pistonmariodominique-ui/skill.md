---
name: security-audit
description: "Audit et durcissement sécurité d'une app Supabase/Lovable/edge functions et de bots IA : RLS et policies, clés et secrets, authentification des fonctions (cron, webhooks Telegram), exposition de la clé anon côté front, injection de prompt dans les agents LLM, advisors Supabase. Actions : auditer, vérifier, sécuriser, durcir, corriger une faille, revue de sécurité. Sujets : RLS, row level security, policy, anon key, service role, CRON_SECRET, webhook, fail-closed, timing attack, secrets, env vars, prompt injection, signups, XSS, CORS. Utiliser ce skill avant tout déploiement, après tout changement de schéma/policy, et à chaque revue de sécurité."
---

# Security Audit — Supabase, Edge Functions & Bots IA

Skill d'audit défensif pour la stack du projet : base Supabase (RLS), edge functions (crons, webhooks), front Lovable (clé anon publique), et agents IA (Gemini/LLM). Objectif : trouver et corriger les failles AVANT qu'elles coûtent, sans jamais casser la prod.

## ⚠️ Principe fondateur

**La sécurité se vérifie avec des requêtes et des tests, jamais de mémoire.** Un audit qui dit « ça a l'air bon » sans avoir exécuté les vérifications ne vaut rien. Et inversement : **ne jamais durcir à l'aveugle** — une policy resserrée sans vérifier ce que le front consomme casse l'application (panne = aussi un incident). Ordre de travail : mesurer → comprendre qui consomme quoi → corriger → re-vérifier.

## Le modèle de menace de CE projet (à garder en tête)

1. **La clé `anon` est PUBLIQUE** (embarquée dans le front Lovable). Tout ce que les policies RLS autorisent au rôle `anon` est lisible/modifiable par n'importe qui sur Internet.
2. **Les edge functions sont des URLs publiques** (`verify_jwt=false` pour les crons). Sans vérification de secret FAIL-CLOSED, n'importe qui peut déclencher un cycle de trading, spammer Telegram ou brûler les quotas API.
3. **Le rôle `authenticated` n'est PAS un cercle de confiance** : si les inscriptions Supabase Auth sont ouvertes (défaut), n'importe qui peut créer un compte et devenir `authenticated`.
4. **Les LLM lisent des données non fiables** (prix, news, messages Telegram) : une instruction malveillante glissée dans ces données peut détourner la décision de l'IA si les garde-fous ne sont pas en CODE.
5. **Le service role key et les secrets** ne doivent JAMAIS apparaître : dans le code committé, dans les logs, dans les messages Telegram, dans les réponses HTTP d'erreur.

## Workflow d'audit (dans l'ordre, avec preuves)

| # | Couche | Vérifications | Référence |
|---|--------|---------------|-----------|
| 1 | Advisors Supabase | `get_advisors` type security PUIS performance — point de départ, jamais suffisant seul | — |
| 2 | Base / RLS | RLS activé partout, inventaire des policies, qui lit/écrit quoi avec quel rôle | `references/supabase-rls.md` |
| 3 | Auth | Inscriptions ouvertes ?, utilisateurs existants, policies `authenticated` permissives | `references/supabase-rls.md` |
| 4 | Edge functions | Fail-closed sur TOUTES, comparaison temps constant, secrets en env, pas de secret loggé | `references/edge-functions.md` |
| 5 | Front / clés | Ce que la clé anon expose, données sensibles lisibles publiquement | `references/supabase-rls.md` |
| 6 | Agents IA | Anti-injection dans les prompts, limites de risque en CODE pas en prompt, sortie revalidée | `references/llm-security.md` |
| 7 | Rapport | Trier par sévérité, corriger le critique, documenter le reste dans le handoff | ci-dessous |

## Grille de sévérité (trier AVANT de corriger)

| Niveau | Critère | Exemple vécu dans ce projet | Action |
|--------|---------|------------------------------|--------|
| 🔴 CRITIQUE | Exploitable maintenant, impact argent/contrôle | Auth cron fail-open : `CRON_SECRET && ...` → sans secret configuré, tout passait (régression v51→v68, corrigée v70) | Corriger immédiatement, déployer |
| 🟠 ÉLEVÉ | Exploitable sous condition réaliste | Policy UPDATE `USING(true)` pour `authenticated` + inscriptions ouvertes = n'importe qui contrôle `bot_status` | Corriger sous 24-48h, vérifier la dépendance du front d'abord |
| 🟡 MOYEN | Fuite d'information, pas de contrôle | `telegram_logs` (chat_id + messages) et toute la stratégie lisibles avec la clé anon | Planifier, tester l'impact UI avant |
| 🔵 FAIBLE | Défense en profondeur | `pg_net` dans le schéma public, comparaison de secret non temps-constant | Backlog, corriger au prochain passage |

## Les 8 règles d'or

1. **Fail-closed partout** : secret absent/invalide → tout refuser. Le motif `if (SECRET && header !== SECRET)` est une faille (si SECRET est vide, tout passe). Écrire `if (!SECRET || !constantTimeEqual(header, SECRET)) → 401`.
2. **RLS activé sur toutes les tables**, et une policy = une intention explicite. `USING(true)` en UPDATE/DELETE/INSERT est presque toujours une erreur.
3. **La clé anon ne doit voir que ce qu'un inconnu peut voir.** Se demander pour chaque table : « suis-je à l'aise si c'est sur pastebin ? »
4. **Signups fermés** (ou email confirmé + allowlist) tant que l'app n'est pas multi-utilisateurs.
5. **Secrets uniquement en variables d'environnement**, jamais en dur, jamais dans les logs (`console.error(JSON.stringify(data))` sur une réponse d'API peut logger un token), jamais dans les messages Telegram.
6. **Les limites de risque et permissions vivent en CODE, jamais dans un prompt LLM** — un prompt se contourne, du code non.
7. **Tout durcissement passe par : inventaire des consommateurs → changement → test du front → rollback prêt.** Ne jamais casser la prod pour un 🟡.
8. **Chaque audit finit par un écrit** : findings triés, corrigés/restants, dans le handoff du projet — le prochain agent ne doit pas re-découvrir.

## Anti-patterns à refuser

| Demande | Pourquoi refuser | Alternative |
|---------|------------------|-------------|
| « Désactive RLS, c'est plus simple » | Toute la base devient publique via l'anon key | Policies explicites par rôle |
| « Mets le service role key dans le front » | Contrôle total de la base pour tout visiteur | Edge function côté serveur |
| « Loggue la réponse complète pour débugger » | Les réponses d'API contiennent parfois tokens/PII | Logger code d'erreur + champs choisis |
| « Le prompt dit à l'IA de refuser, ça suffit » | L'injection de prompt contourne les consignes | Garde-fous en code + revalidation de sortie |
| « On sécurisera après la mise en prod » | La fenêtre d'exposition, c'est maintenant | Audit AVANT chaque déploiement |
