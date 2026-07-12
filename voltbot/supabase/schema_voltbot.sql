-- VoltBot — Schéma de la base de données (Supabase, projet "jarvis-mario", partagé avec ForexBot)
-- Appliqué le 2026-07-11 via la migration `voltbot_init`.
-- Tables préfixées volt_* : totalement isolées de ForexBot (aucune table existante modifiée).
-- Ne contient AUCUN secret — les clés (Capital.com, Gemini, Telegram…) restent dans Supabase Secrets.

CREATE TABLE public.volt_bot_status (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  is_running boolean DEFAULT false,
  mode text DEFAULT 'demo' CHECK (mode = ANY (ARRAY['demo'::text, 'live'::text])),
  balance numeric,
  consecutive_errors integer DEFAULT 0,
  cycle_lock timestamptz,   -- verrou anti-doublon volt-trader (TTL 4 min, cron 5 min)
  monitor_lock timestamptz, -- verrou anti-doublon volt-monitor (TTL 55 s, cron 1 min)
  last_eur_usd numeric,     -- v3 : dernier taux EUR/USD connu (secours crypto week-end)
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE public.volt_settings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  broker text DEFAULT 'Capital.com',
  environment text DEFAULT 'DEMO',
  -- v3 : 7 instruments volatils, crypto 24/7 compris (epics vérifiés sur le démo le 11/07/2026)
  instruments text[] DEFAULT ARRAY['GOLD','SILVER','NATURALGAS','OIL_CRUDE','US30','BTCUSD','ETHUSD']::text[],
  timeframe text DEFAULT 'M15',
  risk_pct numeric DEFAULT 0.5,          -- % du capital risqué par trade (plafonné 1.0 dans le code)
  min_confidence numeric DEFAULT 0.70,
  atr_sl_mult numeric DEFAULT 1.5,       -- hérité v2 (v3 : SL = 2×ATR M5 borné 0.6-1.5×ATR M15)
  atr_tp_mult numeric DEFAULT 3.0,       -- hérité v2 (v3 : plus de TP fixe — trailing ATR)
  trail_atr_mult numeric DEFAULT 2.5,    -- v3 : sortie gagnante = retracement de X×ATR depuis le pic
  vol_ratio_min numeric DEFAULT 0.7,     -- sous ce ratio : marché endormi, pas de trade
  vol_ratio_max numeric DEFAULT 3.0,     -- au-dessus : chaos, pas de trade
  max_open_trades integer DEFAULT 3,
  max_trades_per_day integer DEFAULT 8,
  daily_loss_limit numeric DEFAULT 20,
  weekly_loss_limit numeric DEFAULT 60,
  sizing_capital_cap numeric,            -- NULL = pas de plafond de capital pour le sizing
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE public.volt_trades (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  instrument text, -- v3 : plus de CHECK — la liste des instruments est contrôlée par le code
  direction text CHECK (direction = ANY (ARRAY['BUY'::text, 'SELL'::text])),
  entry_price numeric,
  exit_price numeric,
  size numeric,
  profit_loss numeric,                   -- provisoire à la fermeture, réel après réconciliation
  status text DEFAULT 'OPEN' CHECK (status = ANY (ARRAY['OPEN'::text, 'CLOSED'::text, 'CANCELLED'::text])),
  deal_reference text,                   -- dealReference Capital.com renvoyé à l'ouverture
  broker_deal_id text,                   -- dealId réel (base de la réconciliation P&L)
  atr_at_open numeric,
  vol_ratio_at_open numeric,
  sl_price numeric,                      -- SL du BOT (serré, ATR M5) — le stop garanti broker est plus large
  tp_price numeric,                      -- v3 : NULL — la sortie gagnante est le trailing ATR du moniteur
  max_pnl_points numeric DEFAULT 0,      -- pic de gain (unités de prix) pour le trailing
  breakeven_triggered boolean DEFAULT false,
  close_reason text,
  is_clean_trade boolean DEFAULT true,   -- false = fantôme (jamais ouvert chez Capital), exclu des stats
  pnl_reconciled boolean DEFAULT false,  -- true = P&L lu depuis /history/transactions Capital
  opened_at timestamptz DEFAULT now(),
  closed_at timestamptz
);

CREATE TABLE public.volt_signals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  instrument text,
  direction text,
  confidence numeric,
  reasoning text,
  regime text,
  atr numeric,
  vol_ratio numeric,
  executed boolean DEFAULT false,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE public.volt_performance (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  date date DEFAULT CURRENT_DATE UNIQUE,
  total_trades integer DEFAULT 0,
  winning_trades integer DEFAULT 0,
  total_pnl numeric DEFAULT 0,
  win_rate numeric DEFAULT 0
);

CREATE TABLE public.volt_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  chat_id text,
  message text,
  direction text CHECK (direction = ANY (ARRAY['IN'::text, 'OUT'::text])),
  created_at timestamptz DEFAULT now()
);

-- RLS : même modèle que ForexBot — lecture seule pour le dashboard (anon),
-- écriture réservée aux fonctions Edge (service_role, bypass RLS).
ALTER TABLE public.volt_bot_status ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.volt_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.volt_trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.volt_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.volt_performance ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.volt_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "read_only_dashboard" ON public.volt_bot_status FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "read_only_dashboard" ON public.volt_settings FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "read_only_dashboard" ON public.volt_trades FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "read_only_dashboard" ON public.volt_signals FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "read_only_dashboard" ON public.volt_performance FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "read_only_dashboard" ON public.volt_logs FOR SELECT TO anon, authenticated USING (true);

-- Exception (comme bot_status ForexBot) : bouton Start/Stop du dashboard
CREATE POLICY "dashboard_toggle_bot" ON public.volt_bot_status
FOR UPDATE TO anon, authenticated
USING (true)
WITH CHECK (true);

-- Lignes initiales (1 ligne chacune)
INSERT INTO public.volt_bot_status (is_running, mode) VALUES (false, 'demo');
INSERT INTO public.volt_settings DEFAULT VALUES;
