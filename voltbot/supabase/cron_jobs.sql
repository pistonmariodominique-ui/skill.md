-- VoltBot — Tâches planifiées (pg_cron, Supabase jarvis-mario)
-- Créées le 2026-07-11 (jobid 7 et 8). Le header x-cron-secret a été copié en SQL
-- depuis le job forexbot-scan existant — le secret ne quitte jamais la base.
--
-- ⚠️ Pour recréer à l'identique : remplacer <CRON_SECRET> par la valeur stockée
-- dans Supabase Secrets (jamais écrite en clair dans ce fichier).

-- 1. volt-scan — analyse + ouverture (7 instruments, thèse M15 + entrée M5), toutes les 5 min
-- (le LLM n'est appelé qu'une fois par fenêtre de 14 min et par instrument — cache de thèse)
SELECT cron.schedule(
  'volt-scan',
  '*/5 * * * *',
  $$
  SELECT net.http_post(
    url := 'https://qjnbjslenxsnfrhmlbxn.supabase.co/functions/v1/volt-trader',
    headers := '{"Content-Type": "application/json", "x-cron-secret": "<CRON_SECRET>"}'::jsonb,
    body := '{}'::jsonb
  ) AS request_id;
  $$
);

-- 2. volt-monitor — surveillance SL/TP bot, breakeven, trailing, time-stops,
--    fermeture broker, réconciliation P&L réel — chaque minute
SELECT cron.schedule(
  'volt-monitor',
  '* * * * *',
  $$
  SELECT net.http_post(
    url := 'https://qjnbjslenxsnfrhmlbxn.supabase.co/functions/v1/volt-monitor',
    headers := '{"Content-Type": "application/json", "x-cron-secret": "<CRON_SECRET>"}'::jsonb,
    body := '{}'::jsonb
  ) AS request_id;
  $$
);

-- Note : volt-trader et volt-monitor sont déployés SANS vérification JWT
-- (auth personnalisée x-cron-secret fail-closed, comparaison temps constant),
-- comme les fonctions ForexBot.
