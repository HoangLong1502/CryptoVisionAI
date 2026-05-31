'use client';

import { TrendingDown, TrendingUp } from 'lucide-react';

export type WatchlistRow = {
  symbol: string;
  name?: string;
  price: number;
  change: number;
  change_pct?: number;
  volume_24h?: number;
  signal_label?: string;
};

function fmtUsd(v: number) {
  if (!v || v <= 0) return '—';
  if (v >= 1) return `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  return `$${v.toFixed(6)}`;
}

function fmtPct(v: number) {
  const sign = v >= 0 ? '+' : '';
  return `${sign}${v.toFixed(2)}%`;
}

export default function CoinWatchlist({
  watchlist,
  onDetail,
}: {
  readonly watchlist: WatchlistRow[];
  readonly onDetail: (symbol: string) => void;
}) {
  return (
    <section className="section-card">
      <div className="mb-4 flex items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-bold text-white">Live prices</h2>
          <p className="text-xs text-slate-500">WebSocket updates ~every 10s · CoinGecko</p>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-left text-sm">
          <thead>
            <tr className="border-b border-white/5 text-xs uppercase tracking-wider text-slate-500">
              <th className="pb-3 pr-4">Coin</th>
              <th className="pb-3 pr-4 text-right">Price (USD)</th>
              <th className="pb-3 pr-4 text-right">24h</th>
              <th className="pb-3 pr-4 text-right hidden sm:table-cell">24h Volume</th>
              <th className="pb-3 text-right">Detail</th>
            </tr>
          </thead>
          <tbody>
            {watchlist.map((row) => {
              const ch = row.change_pct ?? row.change ?? 0;
              const up = ch >= 0;
              return (
                <tr key={row.symbol} className="border-b border-white/5 last:border-0">
                  <td className="py-3 pr-4">
                    <p className="font-mono font-bold text-white">{row.symbol}</p>
                    {row.name ? <p className="text-xs text-slate-500">{row.name}</p> : null}
                  </td>
                  <td className="py-3 pr-4 text-right font-mono tabular-nums text-slate-100">{fmtUsd(row.price)}</td>
                  <td className="py-3 pr-4 text-right">
                    <span
                      className={`inline-flex items-center gap-1 font-mono text-xs font-semibold tabular-nums ${
                        up ? 'text-emerald-400' : 'text-rose-400'
                      }`}
                    >
                      {up ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                      {fmtPct(ch)}
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-right font-mono text-xs text-slate-500 hidden sm:table-cell">
                    {row.volume_24h ? `$${(row.volume_24h / 1e6).toFixed(1)}M` : '—'}
                  </td>
                  <td className="py-3 text-right">
                    <button
                      type="button"
                      onClick={() => onDetail(row.symbol)}
                      className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs font-semibold text-amber-200 hover:bg-amber-500/20"
                    >
                      Detail
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
