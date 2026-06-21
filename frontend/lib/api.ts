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

export type PaperHolding = {
  symbol: string;
  quantity: number;
  avg_buy_price: number;
  current_price: number;
  cost_usd: number;
  value_usd: number;
  pnl_usd: number;
  pnl_pct: number;
  change_24h_pct: number;
};

export type PaperWalletSnapshot = {
  mode: string;
  cash_usd: number;
  initial_balance_usd: number;
  holdings_value_usd: number;
  total_equity_usd: number;
  total_pnl_usd: number;
  total_pnl_pct: number;
  holdings_pnl_usd: number;
  holdings_pnl_pct: number;
  holdings: PaperHolding[];
  trade_count: number;
};

export type PaperTradeResponse = {
  ok: boolean;
  message: string;
  trade?: { side: string; symbol: string; quantity: number; price: number; amount_usd: number };
  wallet: PaperWalletSnapshot;
};

export async function getPaperWallet(): Promise<PaperWalletSnapshot> {
  const res = await fetchWithTimeout(`${apiUrl}/paper/wallet`, 15_000);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<PaperWalletSnapshot>;
}

export async function paperBuy(symbol: string, amountUsd: number): Promise<PaperTradeResponse> {
  const res = await fetchWithTimeout(`${apiUrl}/paper/buy`, 15_000, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol: symbol.trim().toUpperCase(), amount_usd: amountUsd }),
  });
  const data = (await res.json()) as PaperTradeResponse & { error?: string };
  if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`);
  return data;
}

export async function paperSell(
  symbol: string,
  opts: { quantity?: number; sellAll?: boolean },
): Promise<PaperTradeResponse> {
  const res = await fetchWithTimeout(`${apiUrl}/paper/sell`, 15_000, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      symbol: symbol.trim().toUpperCase(),
      quantity: opts.quantity,
      sell_all: opts.sellAll ?? false,
    }),
  });
  const data = (await res.json()) as PaperTradeResponse & { error?: string };
  if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`);
  return data;
}

export async function paperReset(): Promise<PaperTradeResponse> {
  const res = await fetchWithTimeout(`${apiUrl}/paper/reset`, 15_000, { method: 'POST' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<PaperTradeResponse>;
}

export type AutoTradingAction = {
  at?: string;
  side: 'buy' | 'sell' | string;
  symbol: string;
  amount_usd?: number;
  message?: string;
  ai_verdict?: string;
  ai_confidence?: number;
  skipped?: boolean;
  error?: string;
};

export type AutoTradingStatus = {
  enabled: boolean;
  last_run_at?: string | null;
  last_error?: string | null;
  recent_actions: AutoTradingAction[];
  stats: { total_buys?: number; total_sells?: number; cycles?: number };
  settings: {
    interval_ms: number;
    interval_seconds: number;
    cooldown_seconds: number;
    min_profit_usd: number;
    budget_mode: string;
    max_deploy_pct: number;
  };
};

export async function getAutoTradingStatus(): Promise<AutoTradingStatus> {
  const res = await fetchWithTimeout(`${apiUrl}/paper/auto-trading`, 15_000);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<AutoTradingStatus>;
}

export async function toggleAutoTrading(): Promise<AutoTradingStatus & { cycle?: unknown }> {
  const res = await fetchWithTimeout(`${apiUrl}/paper/auto-trading/toggle`, 120_000, { method: 'POST' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<AutoTradingStatus & { cycle?: unknown }>;
}

export type PnlPoint = {
  at: string;
  label: string;
  pnl_usd: number;
  pnl_pct: number;
};

export type PerformanceChartData = {
  days: number;
  retention_days: number;
  point_count: number;
  auto: PnlPoint[];
  manual: PnlPoint[];
  total: PnlPoint[];
  latest?: Record<string, number | string> | null;
};

export async function getPerformanceWeek(): Promise<PerformanceChartData> {
  const res = await fetchWithTimeout(`${apiUrl}/paper/performance/week`, 15_000);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<PerformanceChartData>;
}

export async function getPerformanceMonth(): Promise<PerformanceChartData> {
  const res = await fetchWithTimeout(`${apiUrl}/paper/performance/month`, 15_000);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<PerformanceChartData>;
}

export type CoinSearchResult = {
  symbol: string;
  name: string;
  coin_id: string;
  market_cap_rank?: number | null;
  already_listed?: boolean;
};

export type WatchlistAddResponse = {
  ok: boolean;
  symbol: string;
  name: string;
  coin_id: string;
  binance_pair?: string | null;
  has_live_price?: boolean;
  is_custom?: boolean;
  message: string;
};

export async function searchCoins(query: string): Promise<CoinSearchResult[]> {
  const q = query.trim();
  if (!q) return [];
  const res = await fetchWithTimeout(`${apiUrl}/watchlist/search?q=${encodeURIComponent(q)}`, 15_000);
  if (!res.ok) return [];
  const data = (await res.json()) as { results?: CoinSearchResult[] };
  return data.results ?? [];
}

export async function addWatchlistCoin(opts: { symbol?: string; coinId?: string }): Promise<WatchlistAddResponse> {
  const res = await fetchWithTimeout(`${apiUrl}/watchlist/add`, 20_000, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      symbol: opts.symbol?.trim().toUpperCase() || undefined,
      coin_id: opts.coinId?.trim().toLowerCase() || undefined,
    }),
  });
  const data = (await res.json()) as WatchlistAddResponse & { error?: string };
  if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`);
  return data;
}

export async function removeWatchlistCoin(symbol: string): Promise<{ ok: boolean; message: string }> {
  const sym = symbol.trim().toUpperCase();
  const res = await fetchWithTimeout(`${apiUrl}/watchlist/${encodeURIComponent(sym)}`, 15_000, {
    method: 'DELETE',
  });
  const data = (await res.json()) as { ok?: boolean; message?: string; error?: string };
  if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`);
  return { ok: true, message: data.message ?? `Removed ${sym}` };
}
