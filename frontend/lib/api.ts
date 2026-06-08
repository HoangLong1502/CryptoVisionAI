import { WATCHLIST_FALLBACK_SYMBOLS } from './watchlist-symbols';

export { WATCHLIST_FALLBACK_SYMBOLS };

export const apiUrl = (() => {
  if (typeof window === 'undefined') {
    return process.env.INTERNAL_API_URL ?? 'http://backend:8000/api/v1';
  }
  // Same-origin proxy via next.config rewrites — avoids CORS and port mismatch
  return process.env.NEXT_PUBLIC_API_URL ?? '/api/v1';
})();

export function marketWsUrl(): string {
  if (typeof window === 'undefined') {
    return 'ws://127.0.0.1:5566/ws/market';
  }
  const host = window.location.hostname || 'localhost';
  const port = process.env.NEXT_PUBLIC_WS_PORT ?? '5566';
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${host}:${port}/ws/market`;
}

const SSR_FETCH_MS = 30_000;
const AGENT_LONG_FETCH_MS = 120_000;

async function fetchWithTimeout(url: string, ms: number, init?: RequestInit): Promise<Response> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  try {
    return await fetch(url, { cache: 'no-store', signal: ctrl.signal, ...init });
  } finally {
    clearTimeout(t);
  }
}

export type CoinDetailData = {
  symbol: string;
  name?: string;
  rank?: number;
  prices?: {
    last: number;
    high_24h: number;
    low_24h: number;
    ath: number;
    atl: number;
  };
  change_pct?: number;
  volume_24h?: number;
  market_cap?: number;
  circulating_supply?: number;
  volume_to_mcap_pct?: number;
  order_flow?: {
    pressure?: string;
    pressure_label?: string;
  };
  quote_source?: string;
};

export type UserBrief = {
  headline: string;
  verdict_label: string;
  verdict_tone: string;
  summary: string;
  action: string;
  user_holdings?: number;
  position_value_usd?: number;
  insights: Array<{
    category: string;
    title: string;
    text: string;
    tone: 'positive' | 'negative' | 'warning' | 'neutral';
  }>;
  warnings: string[];
  positives: string[];
  votes: { buy: number; hold: number; sell: number };
  agent_lines?: Array<{
    agent: string;
    agent_label: string;
    verdict_label: string;
    one_liner: string;
  }>;
  timing_forecast?: TimingForecast;
};

export type TimingForecast = {
  symbol?: string;
  current_price?: number;
  buy_window: {
    start_date: string;
    end_date: string;
    label: string;
    entry_price_low: number;
    entry_price_high: number;
    entry_price_ideal: number;
    recommended: boolean;
    note: string;
  };
  sell_window: {
    start_date: string;
    end_date: string;
    label: string;
    target_price_low: number;
    target_price_high: number;
    target_price_base: number;
    stop_loss: number;
    expected_gain_pct: number;
    note: string;
  };
  confidence: 'high' | 'medium' | 'low';
  methodology?: string;
  disclaimer?: string;
};

export type DebateResponse = {
  symbol: string;
  user_holdings?: number;
  user_brief?: UserBrief;
  debate: Array<{
    agent: string;
    verdict: string;
    confidence: number;
    rationale: string;
  }>;
  consensus: {
    verdict: string;
    confidence: number;
    reasoning?: string;
    agent_votes?: { buy: number; hold: number; sell: number };
  } | null;
  workflow?: {
    title: string;
    agents: Array<{ id: string; role: string }>;
  };
  current_price?: number;
};

export async function getCoinDetail(symbol: string): Promise<CoinDetailData> {
  const sym = symbol.trim().toUpperCase();
  const res = await fetchWithTimeout(`${apiUrl}/market/coin/${encodeURIComponent(sym)}`, 30_000);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<CoinDetailData>;
}

export async function getAgentDebate(symbol: string, holdings: number): Promise<DebateResponse> {
  const sym = symbol.trim().toUpperCase();
  const res = await fetchWithTimeout(
    `${apiUrl}/agents/debate/${encodeURIComponent(sym)}`,
    AGENT_LONG_FETCH_MS,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ holdings: Math.max(0, holdings) }),
    },
  );
  if (!res.ok) {
    return { symbol: sym, debate: [], consensus: null };
  }
  return res.json() as Promise<DebateResponse>;
}

export async function getDashboardData() {
  try {
    const res = await fetchWithTimeout(`${apiUrl}/market/overview`, SSR_FETCH_MS);
    if (!res.ok) {
      return emptyDashboard();
    }
    return res.json();
  } catch {
    return emptyDashboard();
  }
}

function emptyDashboard() {
  return {
    indices: [],
    watchlist: WATCHLIST_FALLBACK_SYMBOLS.map((symbol) => ({ symbol, price: 0, change: 0 })),
    top_gainers: [],
    top_losers: [],
    quote_source: '',
  };
}
