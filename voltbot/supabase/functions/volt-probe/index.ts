// volt-probe — utilitaire de découverte des marchés Capital.com (DEMO)
// Auth x-cron-secret comme les autres fonctions volt-*. Ne trade jamais.
// body: {"search": ["bitcoin", ...]} → résultats de /api/v1/markets?searchTerm=
// body: {"epics": ["BTCUSD", ...]}  → détails de /api/v1/markets/{epic}

const CAPITAL_URL = Deno.env.get('CAPITAL_API_URL') ?? 'https://demo-api-capital.backend-capital.com';
const CAPITAL_KEY = Deno.env.get('CAPITAL_API_KEY') ?? '';
const CAPITAL_EMAIL = Deno.env.get('CAPITAL_EMAIL') ?? '';
const CAPITAL_PASSWORD = Deno.env.get('CAPITAL_PASSWORD') ?? '';
const CRON_SECRET = Deno.env.get('CRON_SECRET') ?? '';

function constantTimeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

async function capitalAuth() {
  const r = await fetch(`${CAPITAL_URL}/api/v1/session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CAP-API-KEY': CAPITAL_KEY },
    body: JSON.stringify({ identifier: CAPITAL_EMAIL, password: CAPITAL_PASSWORD, encryptedPassword: false })
  });
  if (!r.ok) throw new Error(`Auth failed: ${r.status}`);
  return { cst: r.headers.get('CST')!, token: r.headers.get('X-SECURITY-TOKEN')! };
}

Deno.serve(async (req: Request) => {
  const provided = req.headers.get('x-cron-secret') ?? '';
  if (!CRON_SECRET || !constantTimeEqual(provided, CRON_SECRET)) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 401 });
  }
  try {
    const body = await req.json().catch(() => ({}));
    const { cst, token } = await capitalAuth();
    const headers = { 'CST': cst, 'X-SECURITY-TOKEN': token, 'X-CAP-API-KEY': CAPITAL_KEY };
    const out: Record<string, unknown> = {};

    for (const term of (body.search ?? []).slice(0, 10)) {
      const r = await fetch(`${CAPITAL_URL}/api/v1/markets?searchTerm=${encodeURIComponent(term)}`, { headers });
      const data = r.ok ? await r.json() : {};
      out[`search:${term}`] = (data.markets ?? []).slice(0, 6).map((m: any) => ({
        epic: m.epic, name: m.instrumentName, type: m.instrumentType,
        status: m.marketStatus, bid: m.bid, offer: m.offer
      }));
    }

    for (const epic of (body.epics ?? []).slice(0, 12)) {
      const r = await fetch(`${CAPITAL_URL}/api/v1/markets/${encodeURIComponent(epic)}`, { headers });
      if (!r.ok) { out[`epic:${epic}`] = { error: `HTTP ${r.status}` }; continue; }
      const d = await r.json();
      const bid = d.snapshot?.bid, offer = d.snapshot?.offer;
      const mid = bid && offer ? (bid + offer) / 2 : 0;
      const gsl = d.dealingRules?.minGuaranteedStopDistance ?? d.dealingRules?.minControlledRiskStopDistance;
      out[`epic:${epic}`] = {
        name: d.instrument?.name, type: d.instrument?.type,
        status: d.snapshot?.marketStatus, bid, offer,
        spreadPctOfPrice: mid ? Math.round(((offer - bid) / mid) * 100000) / 1000 : null,
        minDealSize: d.dealingRules?.minDealSize?.value,
        minGsl: gsl ? `${gsl.value} ${gsl.unit}` : null,
        marginFactor: d.instrument?.marginFactor,
        openingHours: d.instrument?.openingHours ?? null
      };
    }

    return new Response(JSON.stringify(out), { headers: { 'Content-Type': 'application/json' } });
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), { status: 500 });
  }
});
