# Edge functions : authentification, secrets, webhooks

Les edge functions en `verify_jwt=false` sont des **URLs publiques**. Chacune
doit porter sa propre défense. Auditer TOUTES les fonctions (`list_edge_functions`
puis `get_edge_function` pour lire le code réellement déployé — pas celui du
dépôt, qui peut être en retard).

## 1. Authentification fail-closed (le point n°1, faille vécue dans ce projet)

❌ **Faille (régression v51→v68 de capital-trader, corrigée en v70)** :
```ts
if (CRON_SECRET && req.headers.get('x-cron-secret') !== CRON_SECRET) return 401;
// Si CRON_SECRET n'est pas configuré (env oubliée, typo de nom), la condition
// est fausse → TOUT LE MONDE PASSE. Fail-open silencieux.
```

✅ **Correct — fail-closed + temps constant** :
```ts
function constantTimeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}
const provided = req.headers.get('x-cron-secret') ?? '';
if (!CRON_SECRET || !constantTimeEqual(provided, CRON_SECRET)) {
  return new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 401 });
}
```

Checklist par fonction :
- [ ] Refuse quand le secret d'env est absent (tester mentalement `SECRET=''`).
- [ ] Comparaison en temps constant (pas de `===` direct sur un secret).
- [ ] Renvoie 401 générique — ne jamais dire « secret invalide » vs « manquant ».
- [ ] Chaque fonction interne appelée par une autre (ex. `technical-agent`) a
      SON secret dédié (`x-tech-secret`) avec la même rigueur.

## 2. Webhooks entrants (Telegram)

- Configurer le webhook Telegram avec `secret_token` (paramètre de `setWebhook`) ;
  Telegram renvoie alors l'en-tête `X-Telegram-Bot-Api-Secret-Token` → le
  vérifier fail-closed comme ci-dessus. Sans ça, n'importe qui peut poster de
  faux messages « venant de Telegram » et piloter le bot.
- Filtrer par `chat_id` autorisé (allowlist en env, pas en base modifiable).
- Traiter le contenu des messages comme NON FIABLE (voir llm-security.md) :
  jamais interpolé dans du SQL, jamais exécuté, jamais réinjecté brut dans un
  prompt avec des privilèges.

## 3. Secrets et fuites dans les logs / messages

- Tous les secrets en `Deno.env.get(...)` — jamais en dur, jamais committés. ✅
- **Pièges de fuite à chercher dans le code** :
  - `console.error(JSON.stringify(data))` sur une réponse d'API tierce : peut
    logger des tokens de session (CST/X-SECURITY-TOKEN chez Capital.com).
  - Messages Telegram d'erreur qui recopient `rawResponse` : même risque, en
    plus visible. Tronquer et choisir les champs.
  - URLs avec clé en query string (`?token=...`, `?key=...`) : apparaissent
    dans les logs de proxys. Préférer les en-têtes quand l'API le permet.
- Rotation : si un secret a pu fuiter (log, commit, message), on le CHANGE, on
  ne débat pas.

## 4. Robustesse = sécurité

- `AbortSignal.timeout(...)` sur tout fetch sortant (une API tierce qui pend ne
  doit pas bloquer un cycle).
- Verrous anti-double-exécution pour les crons (UPDATE atomique avec cutoff —
  déjà en place : `cycle_lock`/`monitor_lock`) : un cron livré deux fois ne doit
  jamais doubler un ordre.
- Idempotence des écritures critiques : `UPDATE ... WHERE status='OPEN'` avec
  contrôle du nombre de lignes touchées avant d'agir (déjà en place).
- Les erreurs 500 ne doivent pas renvoyer de stack trace détaillée au client.

## 5. Après chaque déploiement

1. `get_edge_function` → vérifier que le contenu déployé est IDENTIQUE au dépôt.
2. `get_logs(service=edge-function)` → aucun 500 au boot, aucune fuite de secret.
3. Tester un appel SANS secret → doit répondre 401.
4. Committer le code déployé dans le dépôt (la prod et Git ne doivent jamais diverger).
