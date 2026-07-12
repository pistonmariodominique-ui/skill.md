// volt-monitor — Version 3 (2026-07-12) — VoltBot : surveillance « trend hunter »
// v3 — SORTIE GAGNANTE PAR TRAILING ATR (chandelier) :
//   - Plus de take-profit fixe : après un pic ≥ 1×SL, on sort quand le prix retrace
//     trail_atr_mult × ATR(ouverture) depuis le plus haut atteint. Les gagnants courent.
//   - Breakeven armé à +1×SL (le trade ne peut plus perdre), conservé.
//   - 7 instruments (Or, Argent, Gaz, Pétrole, US30, BTC, ETH). Le crypto est surveillé
//     24/7 : plus de blocage week-end global — on se fie au marketStatus du broker
//     par instrument. Fermetures EOD/vendredi réservées aux instruments non-24/7 ;
//     le crypto a un plafond absolu de 24h par trade (thèse M15 périmée au-delà).
// v2 : TTL du verrou 55 s (vraie cadence 1 min). Conservé.
// Hérité du trade-monitor v38 de ForexBot : réconciliation du P&L RÉEL via
// /history/transactions (matching dealId restreint aux epics VoltBot), adoption des
// positions orphelines, détection « fermé par le broker » (stop garanti déclenché).

import { createClient } from 'jsr:@supabase/supabase-js@2';

const CAPITAL_URL = Deno.env.get('CAPITAL_API_URL') ?? 'https://demo-api-capital.backend-capital.com';
const CAPITAL_KEY = Deno.env.get('CAPITAL_API_KEY') ?? '';
const CAPITAL_EMAIL = Deno.env.get('CAPITAL_EMAIL') ?? '';
const CAPITAL_PASSWORD = Deno.env.get('CAPITAL_PASSWORD') ?? '';
const TELEGRAM_TOKEN = Deno.env.get('TELEGRAM_BOT_TOKEN') ?? '';
const SUPABASE_URL = Deno.env.get('SUPABASE_URL') ?? '';
const SUPABASE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '';
const CRON_SECRET = Deno.env.get('CRON_SECRET') ?? '';
const ADMIN_CHAT_ID = Deno.env.get('TELEGRAM_ADMIN_CHAT_ID') ?? '';

const TIME_STOP_MS = 2 * 60 * 60 * 1000;        // 2h : re-jugement des trades qui ne partent pas
const TIME_STOP_MAX_MS = 2.5 * 60 * 60 * 1000;  // 2h30 : plafond des perdants
const WINNER_MAX_MS = 6 * 60 * 60 * 1000;       // 6h : plafond des gagnants SANS breakeven (pas encore un vrai runner)
const RUNNER_MAX_MS = 24 * 60 * 60 * 1000;      // 24h : plafond absolu d'un runner (crypto surtout)
const TRAIL_ATR_MULT_DEFAULT = 2.5;
const EOD_HOUR_PARIS = 22;
const FRIDAY_EOD_HOUR_UTC = 19;
const RECONCILE_WINDOW_MS = 96 * 60 * 60 * 1000;
const RECONCILE_SETTLE_MS = 6 * 60 * 60 * 1000;

// Instruments (epics = clés). is247 : pas de fermeture EOD/week-end (crypto).
const INSTRUMENT_META: Record<string, { is247: boolean }> = {
  GOLD: { is247: false }, SILVER: { is247: false }, NATURALGAS: { is247: false },
  OIL_CRUDE: { is247: false }, US30: { is247: false },
  BTCUSD: { is247: true }, ETHUSD: { is247: true },
};
const VOLT_EPICS = new Set(Object.keys(INSTRUMENT_META));

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

const pDate = (iso: string) => new Date(iso).toLocaleString('sv-SE', { timeZone: 'Europe/Paris' }).split(' ')[0];

function capHeaders(cst: string, token: string) {
  return { 'CST': cst, 'X-SECURITY-TOKEN': token, 'X-CAP-API-KEY': CAPITAL_KEY };
}

async function capitalAuth() {
  let lastStatus = 0;
  for (let attempt = 1; attempt <= 3; attempt++) {
    const r = await fetch(`${CAPITAL_URL}/api/v1/session`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CAP-API-KEY': CAPITAL_KEY },
      body: JSON.stringify({ identifier: CAPITAL_EMAIL, password: CAPITAL_PASSWORD, encryptedPassword: false })
    });
    if (r.ok) return { cst: r.headers.get('CST')!, token: r.headers.get('X-SECURITY-TOKEN')! };
    lastStatus = r.status;
    if (attempt < 3) await new Promise(res => setTimeout(res, 2000));
  }
  throw new Error(`Auth failed: ${lastStatus}`);
}

async function getPrice(cst: string, token: string, epic: string) {
  const r = await fetch(`${CAPITAL_URL}/api/v1/markets/${epic}`, { headers: capHeaders(cst, token) });
  const data = await r.json();
  return {
    bid: data.snapshot?.bid,
    offer: data.snapshot?.offer,
    marketStatus: String(data.snapshot?.marketStatus ?? '').toUpperCase()
  };
}

async function getRecentCandles(cst: string, token: string, epic: string) {
  const r = await fetch(`${CAPITAL_URL}/api/v1/prices/${epic}?resolution=MINUTE_15&max=3`, {
    headers: capHeaders(cst, token)
  });
  const data = await r.json();
  return data.prices ?? [];
}

async function closeTrade(cst: string, token: string, dealReference: string, epic?: string, entryPrice?: number): Promise<{ success: boolean; reason: string; dealId?: string }> {
  if (!dealReference || dealReference === 'N/A' || dealReference.startsWith('ERREUR')) {
    return { success: false, reason: 'INVALID_REF' };
  }
  try {
    const listR = await fetch(`${CAPITAL_URL}/api/v1/positions`, { headers: capHeaders(cst, token) });
    if (!listR.ok) return { success: false, reason: 'API_LIST_FAILED' };
    const listData = await listR.json();
    const normalizedRef = dealReference.startsWith('o_') ? dealReference.slice(2) : dealReference;
    let pos = (listData.positions ?? []).find((p: any) =>
      p.position?.dealReference === dealReference ||
      p.position?.dealReference === normalizedRef ||
      p.position?.dealId === dealReference
    );
    if (!pos && epic) {
      const tolerance = (entryPrice ?? 0) * 0.001;
      pos = (listData.positions ?? []).find((p: any) =>
        p.market?.epic === epic &&
        (entryPrice == null || Math.abs((p.position?.level ?? 0) - entryPrice) < tolerance)
      );
    }
    if (!pos) return { success: true, reason: 'ALREADY_CLOSED_BY_BROKER' };
    const dealId = pos.position?.dealId;
    if (!dealId) return { success: false, reason: 'DEAL_ID_NOT_FOUND' };
    const r = await fetch(`${CAPITAL_URL}/api/v1/positions/${dealId}`, {
      method: 'DELETE', headers: capHeaders(cst, token)
    });
    return r.ok ? { success: true, reason: 'CLOSED_BY_BOT', dealId } : { success: false, reason: `API_DELETE_FAILED_${r.status}` };
  } catch (err) {
    return { success: false, reason: `NETWORK_ERROR: ${err}` };
  }
}

// P&L réel via /history/transactions (pattern v38) — restreint aux epics VoltBot
type RealTrade = { dealId: string; epic: string; ms: number; net: number };
async function fetchRealizedPnl(cst: string, token: string): Promise<{ ok: boolean; byDeal: Map<string, number>; list: RealTrade[] }> {
  const from = new Date(Date.now() - RECONCILE_WINDOW_MS).toISOString().slice(0, 19);
  const to = new Date().toISOString().slice(0, 19);
  let r: Response;
  try {
    r = await fetch(`${CAPITAL_URL}/api/v1/history/transactions?from=${from}&to=${to}`, { headers: capHeaders(cst, token) });
  } catch (e) { console.error('[fetchRealizedPnl] réseau:', String(e)); return { ok: false, byDeal: new Map(), list: [] }; }
  if (!r.ok) { console.error(`[fetchRealizedPnl] HTTP ${r.status}`); return { ok: false, byDeal: new Map(), list: [] }; }
  const data = await r.json();
  const txs: any[] = data?.transactions ?? [];
  const trades = txs.filter(t => t.transactionType === 'TRADE' && t.dealId && VOLT_EPICS.has(t.instrumentName));
  const fees = txs.filter(t => (t.transactionType === 'TRADE_COMMISSION_GSL' || t.transactionType === 'SWAP') && VOLT_EPICS.has(t.instrumentName))
    .map(f => ({ epic: f.instrumentName, ms: new Date(f.dateUtc).getTime(), size: parseFloat(f.size ?? '0') || 0, used: false }));
  const byDeal = new Map<string, number>();
  const list: RealTrade[] = [];
  for (const t of trades) {
    let net = parseFloat(t.size ?? '0') || 0;
    const tMs = new Date(t.dateUtc).getTime();
    for (const f of fees) {
      if (!f.used && f.epic === t.instrumentName && Math.abs(f.ms - tMs) < 5000) { net += f.size; f.used = true; }
    }
    net = Math.round(net * 100) / 100;
    byDeal.set(t.dealId, net);
    list.push({ dealId: t.dealId, epic: t.instrumentName, ms: tMs, net });
  }
  return { ok: true, byDeal, list };
}

async function getChatId(): Promise<string | null> {
  if (ADMIN_CHAT_ID) return ADMIN_CHAT_ID;
  const { data } = await supabase.from('telegram_logs').select('chat_id')
    .order('created_at', { ascending: false }).limit(1);
  return data?.[0]?.chat_id ?? null;
}

async function sendTelegram(chatId: string | null, text: string) {
  if (!chatId || !TELEGRAM_TOKEN) return;
  const msg = `⚡ *VoltBot*\n${text}`;
  await fetch(`https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: chatId, text: msg, parse_mode: 'Markdown' })
  }).catch((e) => console.error('[telegram]', String(e)));
  await supabase.from('volt_logs').insert({ chat_id: chatId, message: msg, direction: 'OUT' });
}

// P&L provisoire en EUR (USD → EUR) — remplacé par le réel à la réconciliation
function provisionalPnlEur(priceDiff: number, size: number, eurUsd: number | null): number {
  const pnlUsd = priceDiff * size;
  const pnl = eurUsd && eurUsd > 0 ? pnlUsd / eurUsd : pnlUsd;
  return Math.round(pnl * 100) / 100;
}

// volt_performance du jour recalculée depuis les trades (idempotent, pattern v38)
async function recomputePerformance(dateStr: string) {
  const dayStartUtc = new Date(`${dateStr}T00:00:00Z`);
  const from = new Date(dayStartUtc.getTime() - 2 * 3600 * 1000).toISOString();
  const to = new Date(dayStartUtc.getTime() + 26 * 3600 * 1000).toISOString();
  const { data: rows } = await supabase.from('volt_trades')
    .select('profit_loss, closed_at, is_clean_trade')
    .eq('status', 'CLOSED').gte('closed_at', from).lte('closed_at', to);
  const day = (rows ?? []).filter((t: any) => t.is_clean_trade !== false && pDate(t.closed_at) === dateStr);
  const n = day.length;
  const wins = day.filter((t: any) => Number(t.profit_loss) > 0).length;
  const total = Math.round(day.reduce((s: number, t: any) => s + (Number(t.profit_loss) || 0), 0) * 100) / 100;
  const win_rate = n ? Math.round((wins / n) * 100) : 0;
  const { data: existing } = await supabase.from('volt_performance').select('date').eq('date', dateStr).maybeSingle();
  if (existing) {
    await supabase.from('volt_performance').update({ total_trades: n, winning_trades: wins, total_pnl: total, win_rate }).eq('date', dateStr);
  } else {
    await supabase.from('volt_performance').insert({ date: dateStr, total_trades: n, winning_trades: wins, total_pnl: total, win_rate });
  }
}

function constantTimeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

Deno.serve(async (req: Request) => {
  const providedSecret = req.headers.get('x-cron-secret') ?? '';
  if (!CRON_SECRET || !constantTimeEqual(providedSecret, CRON_SECRET)) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 401 });
  }
  try {
    const chatId = await getChatId();

    const { data: statusRow } = await supabase.from('volt_bot_status').select('id, last_eur_usd').single();
    if (statusRow?.id) {
      // TTL 55 s (< période cron de 60 s) : protège contre un chevauchement réel sans
      // sauter un cycle sur deux (un TTL de 100 s ferait tourner le monitor toutes les 2 min).
      const lockCutoff = new Date(Date.now() - 55000).toISOString();
      const { data: lockAcquired } = await supabase.from('volt_bot_status')
        .update({ monitor_lock: new Date().toISOString() })
        .eq('id', statusRow.id)
        .or(`monitor_lock.is.null,monitor_lock.lt.${lockCutoff}`)
        .select('id');
      if (!lockAcquired || lockAcquired.length === 0) {
        return new Response(JSON.stringify({ message: 'Cycle volt-monitor déjà en cours' }), { status: 200 });
      }
    }

    // v3 : PAS de blocage week-end global — le crypto vit 24/7. Chaque trade est
    // géré selon le marketStatus broker de SON instrument.
    const { cst, token } = await capitalAuth();

    const { data: settingsRow } = await supabase.from('volt_settings').select('trail_atr_mult').single();
    const trailMult = parseFloat(String(settingsRow?.trail_atr_mult ?? TRAIL_ATR_MULT_DEFAULT)) || TRAIL_ATR_MULT_DEFAULT;

    // ── Réconciliation du P&L réel (pattern v38) ──
    try {
      const { data: toReconcile } = await supabase.from('volt_trades')
        .select('id, instrument, broker_deal_id, profit_loss, opened_at, closed_at')
        .eq('status', 'CLOSED').eq('pnl_reconciled', false)
        .neq('is_clean_trade', false)
        .gte('closed_at', new Date(Date.now() - RECONCILE_WINDOW_MS).toISOString())
        .order('closed_at', { ascending: true });
      const realized = (toReconcile ?? []).length > 0 ? await fetchRealizedPnl(cst, token) : null;
      if (realized && realized.ok) {
        const { byDeal, list } = realized;
        const idxByDeal = new Map<string, number>(); list.forEach((x, i) => idxByDeal.set(x.dealId, i));
        const usedIdx = new Set<number>();
        const touchedDates = new Set<string>();
        for (const tr of toReconcile!) {
          try {
            const ageClosed = Date.now() - new Date(tr.closed_at).getTime();
            let real: number | undefined; let matchedDeal = tr.broker_deal_id ?? null;
            let reconciledAs: 'real' | 'ghost' | 'abandon' | null = null;
            if (tr.broker_deal_id && byDeal.has(tr.broker_deal_id)) {
              const i = idxByDeal.get(tr.broker_deal_id)!;
              if (!usedIdx.has(i)) { real = list[i].net; usedIdx.add(i); reconciledAs = 'real'; }
            }
            if (real === undefined) {
              const epic = tr.instrument;
              const oMs = new Date(tr.opened_at).getTime(), cMs = new Date(tr.closed_at).getTime() + 5 * 60 * 1000;
              const i = list.findIndex((x, idx) => !usedIdx.has(idx) && x.epic === epic && x.ms >= oMs && x.ms <= cMs);
              if (i >= 0) { real = list[i].net; matchedDeal = list[i].dealId; usedIdx.add(i); reconciledAs = 'real'; }
            }
            if (real === undefined && ageClosed > RECONCILE_SETTLE_MS) reconciledAs = tr.broker_deal_id ? 'abandon' : 'ghost';
            if (!reconciledAs) continue;

            const patch: Record<string, unknown> =
                reconciledAs === 'real' ? { profit_loss: real, pnl_reconciled: true, broker_deal_id: matchedDeal }
              : reconciledAs === 'ghost' ? { is_clean_trade: false, pnl_reconciled: true }
              : { pnl_reconciled: true };
            const { data: done } = await supabase.from('volt_trades').update(patch)
              .eq('id', tr.id).eq('pnl_reconciled', false).select('id');
            if (!done || done.length === 0) continue;
            touchedDates.add(pDate(tr.closed_at));
            if (reconciledAs === 'ghost' && chatId)
              await sendTelegram(chatId, `👻 *Trade fantôme détecté (${tr.instrument})* — jamais ouvert chez Capital, exclu des stats.`);
          } catch (errTr) { console.error(`[reconcile] trade ${tr.id}:`, String(errTr)); }
        }
        for (const d of touchedDates) await recomputePerformance(d);
      }
    } catch (e) { console.error('[reconcile]', String(e)); }

    // ── Adoption des positions orphelines (epics VoltBot uniquement) ──
    const { data: openTradesInitial } = await supabase.from('volt_trades').select('*').eq('status', 'OPEN');
    const openInstruments = new Set((openTradesInitial ?? []).map((t: any) => t.instrument));

    let posListData: any = { positions: [] };
    try {
      const posListR = await fetch(`${CAPITAL_URL}/api/v1/positions`, { headers: capHeaders(cst, token) });
      posListData = posListR.ok ? await posListR.json() : { positions: [] };
      for (const p of (posListData.positions ?? [])) {
        const epicP = p.market?.epic ?? '';
        if (!VOLT_EPICS.has(epicP) || openInstruments.has(epicP)) continue;
        const direction = p.position?.direction ?? null;
        const entryPrice = p.position?.level ?? null;
        const size = p.position?.size ?? null;
        const dealId = p.position?.dealId ?? null;
        if (!direction || !entryPrice || !size || !dealId) continue;

        const tolerance = Number(entryPrice) * 0.001;
        const posCreatedAt = p.position?.createdDateUTC ? new Date(p.position.createdDateUTC) : new Date();
        const windowStart = new Date(posCreatedAt.getTime() - 2 * 60 * 1000).toISOString();
        const windowEnd = new Date(posCreatedAt.getTime() + 2 * 60 * 1000).toISOString();
        const { data: recentSame } = await supabase.from('volt_trades')
          .select('id, entry_price, status, closed_at')
          .eq('instrument', epicP)
          .gte('opened_at', windowStart).lte('opened_at', windowEnd);
        const matching = (recentSame ?? []).filter((t: any) =>
          Math.abs(parseFloat(t.entry_price) - Number(entryPrice)) < tolerance);
        const GRACE_CLOSE_MS = 10 * 60 * 1000;
        const isRaceDuplicate = matching.some((t: any) =>
          t.status === 'OPEN' ||
          (t.closed_at && (Date.now() - new Date(t.closed_at).getTime()) < GRACE_CLOSE_MS));
        if (isRaceDuplicate) continue;

        const { error: insertErr } = await supabase.from('volt_trades').insert({
          instrument: epicP, direction, entry_price: entryPrice, size,
          status: 'OPEN', deal_reference: dealId, broker_deal_id: dealId,
          opened_at: p.position?.createdDateUTC ?? new Date().toISOString()
        });
        if (insertErr) continue;
        openInstruments.add(epicP);
        await sendTelegram(chatId,
          `🔗 *Position orpheline récupérée — ${epicP}*\nDirection: ${direction} | Entrée: ${entryPrice}\nElle est désormais surveillée normalement.`);
      }
    } catch (err) { console.error('[orphelins]', String(err)); }

    // ── Boucle de surveillance ──
    const { data: openTrades } = await supabase.from('volt_trades').select('*').eq('status', 'OPEN');
    const closedResults: any[] = [];

    // Taux EUR/USD (forex fermé le week-end → secours = dernier taux connu en base)
    let eurUsd: number | null = null;
    if ((openTrades ?? []).length > 0) {
      try {
        const fx = await getPrice(cst, token, 'EURUSD');
        if (fx.bid && fx.offer) eurUsd = (fx.bid + fx.offer) / 2;
      } catch { /* secours ci-dessous */ }
      if (!eurUsd) {
        const raw = parseFloat(String(statusRow?.last_eur_usd ?? ''));
        if (Number.isFinite(raw) && raw > 0) eurUsd = raw;
      }
    }

    const nowUtc = new Date();
    const hourParis = parseInt(new Date().toLocaleString('fr-FR', { timeZone: 'Europe/Paris', hour: '2-digit', hour12: false }));
    const isFriday = nowUtc.getUTCDay() === 5;

    for (const trade of (openTrades ?? [])) {
      try {
        const epic = trade.instrument; // v3 : les clés d'instrument SONT les epics
        const is247 = INSTRUMENT_META[epic]?.is247 ?? false;
        const dealRef = trade.deal_reference ?? '';
        const entryPrice = parseFloat(trade.entry_price);

        // Capture du vrai dealId tant que le trade est vivant (base de la réconciliation)
        const tolerance = entryPrice * 0.001;
        const normRef = dealRef.startsWith('o_') ? dealRef.slice(2) : dealRef;
        const posMatch = (posListData.positions ?? []).find((p: any) =>
          p.position?.dealReference === dealRef ||
          p.position?.dealReference === normRef ||
          p.position?.dealId === dealRef ||
          (p.market?.epic === epic && Math.abs((p.position?.level ?? 0) - entryPrice) < tolerance)
        );
        if (posMatch?.position?.dealId && !trade.broker_deal_id) {
          await supabase.from('volt_trades').update({ broker_deal_id: posMatch.position.dealId }).eq('id', trade.id);
          trade.broker_deal_id = posMatch.position.dealId;
        }

        // Position absente du broker → stop garanti déclenché côté Capital entre deux cycles.
        // Grâce de 3 min après l'ouverture (latence de propagation côté broker).
        const ageMs = Date.now() - new Date(trade.opened_at).getTime();
        if (!posMatch && ageMs > 3 * 60 * 1000) {
          const { data: closedData } = await supabase.from('volt_trades').update({
            status: 'CLOSED', closed_at: new Date().toISOString(),
            close_reason: '🏦 Fermé par le broker (stop garanti)', pnl_reconciled: false
          }).eq('id', trade.id).eq('status', 'OPEN').select('id');
          if (closedData && closedData.length > 0) {
            await recomputePerformance(pDate(new Date().toISOString()));
            await sendTelegram(chatId,
              `🏦 *Position fermée par le broker — ${trade.instrument}*\n` +
              `Stop garanti déclenché côté Capital.\n` +
              `P&L réel lu à la réconciliation (prochain cycle).`);
            closedResults.push({ instrument: trade.instrument, reason: 'BROKER_CLOSED' });
          }
          continue;
        }

        const price = await getPrice(cst, token, epic);
        // Marché fermé (pause quotidienne, week-end commodities…) : prix gelés et ordres
        // refusés — on ne prend AUCUNE décision sur cet instrument ce cycle.
        if (price.marketStatus !== 'TRADEABLE') continue;
        const currentPrice = trade.direction === 'BUY' ? price.bid : price.offer;
        if (!currentPrice) continue;

        const pnlDist = trade.direction === 'BUY' ? currentPrice - entryPrice : entryPrice - currentPrice;
        const slPrice = trade.sl_price != null ? parseFloat(trade.sl_price) : null;
        const atrOpen = Number(trade.atr_at_open) || 0;
        const slDist = slPrice != null ? Math.abs(entryPrice - slPrice) : atrOpen * 1.5;

        const hitSL = slPrice != null && (trade.direction === 'BUY' ? currentPrice <= slPrice : currentPrice >= slPrice);
        let shouldClose = hitSL;
        let closeReason = hitSL ? '🛑 Stop-Loss' : '';

        // Suivi du pic de gain (en unités de prix)
        const prevMax = Number(trade.max_pnl_points ?? 0);
        const maxPnl = Math.max(prevMax, pnlDist);
        if (maxPnl > prevMax + slDist * 0.05) {
          await supabase.from('volt_trades').update({ max_pnl_points: Math.round(maxPnl * 10000) / 10000 }).eq('id', trade.id);
        }

        // Breakeven armé à +1×SL : le trade ne peut plus devenir perdant
        if (slDist > 0 && !trade.breakeven_triggered && pnlDist >= slDist) {
          await supabase.from('volt_trades').update({ breakeven_triggered: true }).eq('id', trade.id);
          trade.breakeven_triggered = true;
          await sendTelegram(chatId,
            `🛡️ *Breakeven armé — ${trade.instrument}*\nProfit ≥ 1×SL atteint : le trade ne peut plus perdre. Trailing ATR actif — on le laisse courir.`);
        }
        if (trade.breakeven_triggered && !shouldClose && pnlDist <= 0) {
          shouldClose = true;
          closeReason = '🛡️ Breakeven (profit sécurisé)';
        }

        // ★ TRAILING CHANDELIER (v3) : après un pic ≥ 1×SL, on sort quand le prix a
        // retracé trail_atr_mult × ATR(ouverture) depuis le plus haut. Pas de plafond
        // de gain : c'est LA sortie gagnante du trend hunter.
        if (!shouldClose && atrOpen > 0 && maxPnl >= slDist && (maxPnl - pnlDist) >= trailMult * atrOpen) {
          shouldClose = true;
          const peakAtr = (maxPnl / atrOpen).toFixed(1);
          closeReason = `🏄 Trailing ATR (pic +${peakAtr}×ATR, retracement ${trailMult}×ATR)`;
        }

        // Time-stops — un trade qui ne PART pas est re-jugé ; un runner a de l'air
        if (!shouldClose && ageMs >= TIME_STOP_MS) {
          if (pnlDist >= 0) {
            if (trade.breakeven_triggered) {
              if (ageMs >= RUNNER_MAX_MS) {
                shouldClose = true;
                closeReason = '⏰ Plafond runner (24h — thèse expirée)';
              }
            } else if (ageMs >= WINNER_MAX_MS) {
              shouldClose = true;
              closeReason = '⏰ Time Stop gagnant (6h sans breakeven — thèse M15 expirée)';
            } else if (maxPnl < slDist) {
              const candles = await getRecentCandles(cst, token, epic);
              if (candles.length >= 2) {
                const last = candles[candles.length - 1], prev = candles[candles.length - 2];
                const momentumOk = trade.direction === 'BUY'
                  ? last.closePrice?.bid > prev.closePrice?.bid
                  : last.closePrice?.bid < prev.closePrice?.bid;
                if (!momentumOk) { shouldClose = true; closeReason = '💰 Smart Close (positif, momentum épuisé)'; }
              }
            }
          } else if (ageMs >= TIME_STOP_MAX_MS) {
            shouldClose = true;
            closeReason = '⏰ Time Stop max (2h30)';
          } else if (slDist > 0 && pnlDist > -0.5 * slDist) {
            const candles = await getRecentCandles(cst, token, epic);
            if (candles.length >= 2) {
              const last = candles[candles.length - 1], prev = candles[candles.length - 2];
              const momentumOk = trade.direction === 'BUY'
                ? last.closePrice?.bid > prev.closePrice?.bid
                : last.closePrice?.bid < prev.closePrice?.bid;
              if (!momentumOk) { shouldClose = true; closeReason = '🕐 Time Stop (momentum défavorable)'; }
            } else {
              shouldClose = true; closeReason = '🕐 Time Stop (2h dépassées)';
            }
          } else {
            shouldClose = true; closeReason = '🕐 Time Stop (perte > 50% du SL)';
          }
        }

        // Fin de journée / week-end : instruments NON-24/7 uniquement (gap risk + swap).
        // Le crypto continue — son plafond est le RUNNER_MAX de 24h.
        if (!is247) {
          if (!shouldClose && hourParis >= EOD_HOUR_PARIS) {
            shouldClose = true;
            closeReason = '🌙 Fin de journée (22h Paris — pas de position overnight)';
          }
          if (!shouldClose && isFriday && nowUtc.getUTCHours() >= FRIDAY_EOD_HOUR_UTC) {
            shouldClose = true;
            closeReason = '📅 Vendredi soir — aucune position ne passe le week-end';
          }
        }

        if (shouldClose) {
          const pnlEur = provisionalPnlEur(pnlDist, parseFloat(trade.size), eurUsd);
          const won = pnlDist > 0;

          const { data: closedData } = await supabase.from('volt_trades').update({
            status: 'CLOSED', exit_price: currentPrice,
            profit_loss: pnlEur, closed_at: new Date().toISOString(),
            close_reason: closeReason, pnl_reconciled: false
          }).eq('id', trade.id).eq('status', 'OPEN').select('id');
          if (!closedData || closedData.length === 0) continue;

          const closeResult = await closeTrade(cst, token, dealRef, epic, entryPrice);
          if (closeResult.dealId && !trade.broker_deal_id) {
            await supabase.from('volt_trades').update({ broker_deal_id: closeResult.dealId }).eq('id', trade.id);
          }
          if (!closeResult.success && closeResult.reason !== 'ALREADY_CLOSED_BY_BROKER') {
            await sendTelegram(chatId,
              `⚠️ *Action requise — ${trade.instrument}*\nTrade fermé en base mais *non fermé sur Capital.com*\n→ Ferme manuellement la position\nRef: \`${dealRef}\` | Raison: ${closeResult.reason}`);
          }

          await recomputePerformance(pDate(new Date().toISOString()));
          await sendTelegram(chatId,
            `${won ? '✅' : '❌'} *Trade fermé — ${trade.instrument}*\n${closeReason}\n` +
            `Direction: ${trade.direction}\nEntrée: ${entryPrice} → Sortie: ${currentPrice}\n` +
            `PnL estimé: ~${pnlEur > 0 ? '+' : ''}${pnlEur}€ _(réel au prochain cycle)_`);
          closedResults.push({ instrument: trade.instrument, pnl: pnlEur, won, reason: closeReason });
        }
      } catch (tradeErr) {
        console.error(`[monitor ${trade.instrument}]`, String(tradeErr));
      }
    }

    // ── Watchdog : bot actif mais silencieux depuis 40 min en pleine session ──
    try {
      const { data: st } = await supabase.from('volt_bot_status').select('is_running').single();
      if (st?.is_running && hourParis >= 9 && hourParis < 21) {
        const fortyMinAgo = new Date(Date.now() - 40 * 60 * 1000).toISOString();
        const { count: signalCount } = await supabase.from('volt_signals')
          .select('*', { count: 'exact', head: true }).gte('created_at', fortyMinAgo);
        if ((signalCount ?? 0) === 0) {
          const hourAgo = new Date(Date.now() - 60 * 60 * 1000).toISOString();
          const { count: recentAlert } = await supabase.from('volt_logs')
            .select('*', { count: 'exact', head: true })
            .ilike('message', '%Watchdog%').gte('created_at', hourAgo);
          if ((recentAlert ?? 0) === 0) {
            await sendTelegram(chatId,
              `🔴 *Alerte Watchdog*\nVoltBot actif mais aucune analyse depuis +40 min (${hourParis}h Paris)\n→ Vérifie le cron job volt-scan dans Supabase`);
          }
        }
      }
    } catch { /* best effort */ }

    return new Response(JSON.stringify({ checked: (openTrades ?? []).length, closed: closedResults }), {
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (e) {
    console.error(e);
    return new Response(JSON.stringify({ error: String(e) }), { status: 500 });
  }
});
