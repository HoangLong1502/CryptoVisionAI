'use client';

import { useCallback, useEffect, useState } from 'react';
import { Loader2, Wifi, WifiOff } from 'lucide-react';
import CoinWatchlist from './CoinWatchlist';
import CoinSymbolModal from './CoinSymbolModal';
import FlashPrice from '../ui/FlashPrice';
import { apiUrl, WATCHLIST_FALLBACK_SYMBOLS } from '../../lib/api';
import { useMarketWebSocket } from '../../hooks/useMarketWebSocket';

export type DashboardData = {
  indices: Array<{ symbol: string; price: number; change: number }>;
  watchlist: Array<{
    symbol: string;
    name?: string;
    price: number;
    change: number;
    change_pct?: number;
    volume_24h?: number;
  }>;
  top_gainers: Array<{ symbol: string; change_pct?: number; change?: number }>;
  top_losers: Array<{ symbol: string; change_pct?: number; change?: number }>;
  quote_source?: string;
};

const REFRESH_MS = 120_000;

function emptyDashboard(): DashboardData {
  return {
    indices: [],
    watchlist: WATCHLIST_FALLBACK_SYMBOLS.map((symbol) => ({ symbol, price: 0, change: 0 })),
    top_gainers: [],
    top_losers: [],
  };
}

export default function DashboardHome() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailSymbol, setDetailSymbol] = useState<string | null>(null);
  const { wsConnected } = useMarketWebSocket(data, setData);

  const fetchOverview = useCallback(async () => {
    try {
      const res = await fetch(`${apiUrl}/market/overview`, { cache: 'no-store' });
      if (!res.ok) {
        setData((prev) => prev ?? emptyDashboard());
        return;
      }
      const json = (await res.json()) as DashboardData;
      setData(json);
    } catch {
      setData((prev) => prev ?? emptyDashboard());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOverview();
    const t = setInterval(fetchOverview, REFRESH_MS);
    return () => clearInterval(t);
  }, [fetchOverview]);

  const watchlist = (data?.watchlist ?? []).map((row) =>
    typeof row === 'string' ? { symbol: row, price: 0, change: 0 } : row,
  );

  return (
    <main className="mx-auto max-w-6xl px-4 py-6">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white sm:text-3xl">Crypto Dashboard</h1>
          <p className="mt-1 text-sm text-slate-400">
            Live prices · Coin details · AI committee debate with your holdings
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          {wsConnected ? (
            <>
              <Wifi className="h-4 w-4 text-emerald-400" />
              <span className="text-emerald-400/90">Live</span>
            </>
          ) : (
            <>
              <WifiOff className="h-4 w-4" />
              <span>Connecting to WebSocket…</span>
            </>
          )}
        </div>
      </div>

      {data?.indices && data.indices.length > 0 ? (
        <div className="mb-6 grid gap-3 sm:grid-cols-3">
          {data.indices.map((idx) => (
            <div key={idx.symbol} className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3">
              <p className="text-xs text-slate-500">{idx.symbol}</p>
              <FlashPrice symbol={idx.symbol} price={idx.price} className="font-mono text-lg font-bold text-white">
                {idx.price > 0 ? `$${idx.price.toLocaleString('en-US', { maximumFractionDigits: 2 })}` : '—'}
              </FlashPrice>
              <p className={`text-xs font-mono ${idx.change >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {idx.change >= 0 ? '+' : ''}
                {idx.change.toFixed(2)}%
              </p>
            </div>
          ))}
        </div>
      ) : null}

      {loading && !data ? (
        <div className="flex items-center justify-center gap-2 py-20 text-slate-400">
          <Loader2 className="h-6 w-6 animate-spin" />
          Loading crypto market…
        </div>
      ) : (
        <CoinWatchlist watchlist={watchlist} onDetail={setDetailSymbol} />
      )}

      {data?.quote_source ? <p className="mt-4 text-center text-[10px] text-slate-600">{data.quote_source}</p> : null}

      {detailSymbol ? (
        <CoinSymbolModal
          symbol={detailSymbol}
          livePrice={watchlist.find((w) => w.symbol === detailSymbol)?.price}
          onClose={() => setDetailSymbol(null)}
        />
      ) : null}
    </main>
  );
}
