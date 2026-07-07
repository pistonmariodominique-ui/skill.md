# Supabase : RLS, policies, auth, exposition anon — vérifications concrètes

Toutes les vérifications s'exécutent via les outils MCP Supabase (`execute_sql`,
`get_advisors`). Ne jamais conclure sans avoir exécuté.

## 1. Point de départ : les advisors

`get_advisors(type=security)` puis `type=performance`. C'est le linter officiel
(RLS manquant, policies toujours vraies, extensions dans public, etc.). Il rate
en revanche tout ce qui est **métier** (ex. : « telegram_logs lisible en anon
est-il grave ? ») → toujours compléter par l'inventaire ci-dessous.

## 2. Inventaire complet RLS + policies (LA requête d'audit)

```sql
-- État RLS de chaque table
SELECT c.relname AS tbl, c.relrowsecurity AS rls_on, c.relforcerowsecurity AS rls_forced
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relkind='r' ORDER BY 1;

-- Toutes les policies avec rôle, commande et expression
SELECT tablename, policyname, cmd, roles::text, qual, with_check
FROM pg_policies WHERE schemaname='public' ORDER BY tablename, cmd;
```

Lecture des résultats :
- Table avec `rls_on=false` → 🔴 tout est accessible via l'anon key.
- `rls_on=true` sans aucune policy → accès refusé par défaut (sûr, mais vérifier
  que c'est voulu et que rien côté front n'en dépend).
- Policy `cmd=UPDATE/DELETE/INSERT` avec `qual='true'` ou `with_check='true'`
  → 🟠 quiconque a le rôle peut écrire n'importe quoi. Se demander : QUI a ce
  rôle ? (`anon` = tout Internet ; `authenticated` = tout inscrit).
- Policy `SELECT qual='true'` pour `anon` → fuite d'information : lister ce que
  contient la table et décider (voir §4).

## 3. Auth : qui peut devenir `authenticated` ?

```sql
SELECT count(*) AS nb_users, max(created_at) AS dernier FROM auth.users;
```

- `nb_users = 0` + policies `authenticated` permissives = bombe à retardement :
  si les **inscriptions sont ouvertes** (réglage par défaut), un attaquant crée
  un compte et obtient le rôle. → Vérifier dans le Dashboard : Authentication →
  Sign In / Up → « Allow new users to sign up ». Pour une app mono-utilisateur :
  OFF, ou allowlist d'emails.
- Un nouvel utilisateur inattendu dans `auth.users` = signal d'alerte immédiat.

## 4. Exposition via la clé anon (front Lovable)

La clé anon est dans le bundle JS du front : elle est PUBLIQUE par construction.
Pour chaque table lisible en `anon`, se poser : « à l'aise si c'est sur
pastebin ? ». Dans ce projet :
- `telegram_logs` : contient le **chat_id** (permet de cibler l'utilisateur) et
  tous les messages → à restreindre à `authenticated` dès que le dashboard le
  permet.
- `trades`, `signals`, `bot_settings` : exposent toute la stratégie → fuite
  acceptable en démo, à restreindre avant le passage en réel.

### Procédure de durcissement SANS casser le front (obligatoire)

1. Inventorier ce que le front lit réellement : chercher dans le code du front
   (`src/`) les `from('table')` et noter si l'utilisateur est connecté à ce
   moment-là (route `_authenticated` ≠ garantie : vérifier le client Supabase).
2. Changer UNE policy à la fois (`DROP POLICY` + `CREATE POLICY ... TO authenticated`).
3. Tester le dashboard immédiatement après (les erreurs RLS sont silencieuses
   côté client : la requête renvoie simplement 0 ligne).
4. Garder le SQL de rollback prêt avant de commencer.

## 5. Divers base de données

- Extensions dans `public` (ex. `pg_net`) → les déplacer dans un schéma dédié
  (`extensions`) — attention : utilisées par les crons, tester après.
- Fonctions SQL `SECURITY DEFINER` : vérifier `search_path` épinglé
  (`SET search_path = ''`) sinon élévation de privilèges possible.
- Vues : une vue appartenant à `postgres` contourne le RLS des tables sous-jacentes
  (sauf `security_invoker=true`) — vérifier toute vue exposée à l'API.

## 6. Ce qui est sain et ne doit PAS être « corrigé »

- RLS activé sans policy sur une table interne (deny-all voulu).
- `SELECT USING(true)` sur une table volontairement publique (contenu marketing).
- Les edge functions qui utilisent le service role : c'est leur rôle, côté
  serveur uniquement — le service role key ne doit juste jamais quitter l'env.
