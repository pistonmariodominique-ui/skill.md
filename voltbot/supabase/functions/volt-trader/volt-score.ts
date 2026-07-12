// ═══════════════════════════════════════════════════════════════════════════
// VoltScore ⚡ — version serveur (TypeScript/Deno), même mathématique que le .pine
// ═══════════════════════════════════════════════════════════════════════════
// Module PRÊT À BRANCHER dans volt-trader (voir PLAN-AMELIORATION.md, Palier 4 :
// d'abord en SHADOW MODE — on loggue le score dans volt_signals sans bloquer —
// puis en filtre dur si les données prouvent que score ≥ 70 surperforme).
//
// Différence avec la version TradingView : ici on a le SPREAD réel du broker,
// donc la composante D (qualité d'exécution) combine momentum des bougies
// ET coût du spread relatif à l'ATR.
//
// Usage dans volt-trader :
//   import { computeVoltScore } from './volt-score.ts';
//   const vs = computeVoltScore(candles15m, market.midPrice, spread, ema200H1, settings);
//   → { score, direction, components } ; loguer vs.score dans volt_signals.
// ═══════════════════════════════════════════════════════════════════════════

export type VoltScoreSettings = {
  volMin: number;       // défaut 0.7
  volMax: number;       // défaut 3.0
  volSweetLo: number;   // défaut 1.0
  volSweetHi: number;   // défaut 1.8
  donchLen: number;     // défaut 20
};

export const VOLTSCORE_DEFAULTS: VoltScoreSettings = {
  volMin: 0.7, volMax: 3.0, volSweetLo: 1.0, volSweetHi: 1.8, donchLen: 20,
};

type Candle = {
  openPrice?: { bid?: number }; closePrice?: { bid?: number };
  highPrice?: { bid?: number }; lowPrice?: { bid?: number };
};

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

function trueRanges(h: Candle[]): number[] {
  if (h.length < 2) return [];
  return h.slice(1).map((c, i) => {
    const pc = h[i].closePrice?.bid ?? 0;
    const hi = c.highPrice?.bid ?? 0;
    const lo = c.lowPrice?.bid ?? 0;
    return Math.max(hi - lo, Math.abs(hi - pc), Math.abs(lo - pc));
  });
}

function atr(h: Candle[], period = 14): number {
  const trs = trueRanges(h.slice(-(period + 1)));
  return trs.length ? trs.reduce((a, b) => a + b, 0) / trs.length : 0;
}

function ema(prices: number[], period: number): number {
  if (!prices.length) return 0;
  const data = prices.slice(-Math.max(period * 2, prices.length));
  if (data.length < period) return data.reduce((a, b) => a + b, 0) / data.length;
  const k = 2 / (period + 1);
  let e = data.slice(0, period).reduce((a, b) => a + b, 0) / period;
  for (let i = period; i < data.length; i++) e = data[i] * k + e * (1 - k);
  return e;
}

export type VoltScoreResult = {
  score: number;                 // 0-100 (0 si direction interdite par le 1H)
  direction: 'BUY' | 'SELL' | null;
  components: { vol: number; trend: number; breakout: number; execution: number };
  volRatio: number;
};

/**
 * candles15m : ≥ 60 bougies M15 (200 recommandé, comme le bot)
 * price      : prix mid actuel
 * spread     : offer - bid actuel
 * ema200H1   : EMA200 calculée sur les clôtures 1H (null = filtre 1H inactif)
 */
export function computeVoltScore(
  candles15m: Candle[], price: number, spread: number,
  ema200H1: number | null, s: VoltScoreSettings = VOLTSCORE_DEFAULTS
): VoltScoreResult {
  const closes = candles15m.map(c => c.closePrice?.bid ?? 0).filter(v => v > 0);
  const atr14 = atr(candles15m, 14);
  const allTrs = trueRanges(candles15m);
  const atrRef = allTrs.length >= 30 ? allTrs.reduce((a, b) => a + b, 0) / allTrs.length : atr14;
  const volRatio = atrRef > 0 ? atr14 / atrRef : 1;
  const e20 = ema(closes, 20), e50 = ema(closes, 50);

  // Direction : biais EMA M15, soumis au veto du 1H (règle stricte du bot)
  const biasEma: 1 | -1 = e20 > e50 ? 1 : -1;
  let bias1h: 1 | -1 | 0 = 0;
  if (ema200H1 && ema200H1 > 0) {
    const d = (price - ema200H1) / price;
    bias1h = d > 0.001 ? 1 : d < -0.001 ? -1 : 0;
  }
  const dirOk = bias1h === 0 || biasEma === bias1h;
  const direction: 'BUY' | 'SELL' | null = dirOk ? (biasEma === 1 ? 'BUY' : 'SELL') : null;
  if (!direction || atr14 <= 0) {
    return { score: 0, direction: null, components: { vol: 0, trend: 0, breakout: 0, execution: 0 }, volRatio };
  }

  // A. Expansion de volatilité (0-25) — zone en or [sweetLo, sweetHi]
  let vol = 0;
  if (volRatio >= s.volMin && volRatio <= s.volMax) {
    if (volRatio < s.volSweetLo) vol = 5 + 10 * (volRatio - s.volMin) / Math.max(s.volSweetLo - s.volMin, 0.01);
    else if (volRatio <= s.volSweetHi) vol = 25;
    else vol = 25 * (s.volMax - volRatio) / Math.max(s.volMax - s.volSweetHi, 0.01);
  }
  vol = clamp(vol, 0, 25);

  // B. Force de tendance (0-25) — écart EMA normalisé ATR + alignement 1H
  let trend = clamp(Math.abs(e20 - e50) / atr14, 0, 1) * 18;
  trend += bias1h !== 0 && bias1h === biasEma ? 7 : bias1h === 0 ? 3 : 0;
  trend = clamp(trend, 0, 25);

  // C. Cassure Donchian (0-25) — canal EXCLUANT la bougie courante, fraîcheur décroissante
  const channel = candles15m.slice(-(s.donchLen + 1), -1);
  const dHi = Math.max(...channel.map(c => c.highPrice?.bid ?? 0), 0);
  const dLoArr = channel.map(c => c.lowPrice?.bid ?? 0).filter(v => v > 0);
  const dLo = dLoArr.length ? Math.min(...dLoArr) : 0;
  const lastClose = closes[closes.length - 1];
  let breakout = 0;
  const beyond = direction === 'BUY' ? lastClose - dHi : dLo - lastClose;
  if (beyond > 0) {
    // Fraîcheur : combien de bougies (max 15) clôturaient déjà au-delà du canal ?
    let stale = 0;
    for (let i = closes.length - 2; i >= Math.max(0, closes.length - 16); i--) {
      const past = closes[i];
      const wasBeyond = direction === 'BUY' ? past > dHi : past < dLo;
      if (wasBeyond) stale++; else break;
    }
    breakout = stale <= 2 ? 25 : stale <= 7 ? 15 : stale <= 14 ? 7 : 0;
  } else {
    // Pré-signal : à moins de 0.5×ATR du canal
    const distTo = direction === 'BUY' ? dHi - lastClose : lastClose - dLo;
    if (distTo < 0.5 * atr14) breakout = 8;
  }

  // D. Qualité d'exécution (0-25) — momentum des corps (0-15) + coût du spread (0-10)
  const last3 = candles15m.slice(-3);
  const bodyQ = last3.reduce((acc, c) => {
    const rng = (c.highPrice?.bid ?? 0) - (c.lowPrice?.bid ?? 0);
    const body = (c.closePrice?.bid ?? 0) - (c.openPrice?.bid ?? 0);
    return acc + (rng > 0 ? body / rng : 0);
  }, 0) / 3;
  const momScore = clamp(bodyQ * (direction === 'BUY' ? 1 : -1), 0, 1) * 15;
  const spreadPct = atr14 > 0 ? spread / atr14 : 1;   // filtre dur du bot à 0.25
  const spreadScore = clamp((0.25 - spreadPct) / 0.25, 0, 1) * 10;
  const execution = clamp(momScore + spreadScore, 0, 25);

  const score = Math.round(vol + trend + breakout + execution);
  return { score, direction, components: { vol: Math.round(vol), trend: Math.round(trend), breakout: Math.round(breakout), execution: Math.round(execution) }, volRatio: Math.round(volRatio * 100) / 100 };
}

// Seuils de décision (mêmes que le .pine) :
export const VOLTSCORE_A_PLUS = 70; // setup A+ — ce que le bot doit trader
export const VOLTSCORE_B = 55;      // setup B — surveiller, exiger une confiance LLM plus haute
