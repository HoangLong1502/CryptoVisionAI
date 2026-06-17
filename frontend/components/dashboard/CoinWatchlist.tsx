'use client';

import { Loader2, Plus, TrendingDown, TrendingUp, X } from 'lucide-react';
import FlashPrice from '../ui/FlashPrice';

export type WatchlistRow = {
  symbol: string;
  name?: string;
  price: number;
  change: number;
  change_pct?: number;
  volume_24h?: number;
  signal_label?: string;
  is_custom?: boolean;
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
  onBuy,
  onAdd,
  onRemove,
  removingSymbol,
}: {
  readonly watchlist: WatchlistRow[];
  readonly onDetail: (symbol: string) => void;
  readonly onBuy: (symbol: string) => void;
  readonly onAdd: () => void;
  readonly onRemove?: (symbol: string) => void;
  readonly removingSymbol?: string | null;
}) {
  return (
    <section className="section-card">
      <div className="mb-4 flex items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-bold text-white">Live prices</h2>
          <p className="text-xs text-slate-500">Binance bookTicker · updates ~every 200ms</p>
        </div>
        <button
          type="button"
          onClick={onAdd}
          className="flex items-center gap-1.5 rounded-xl border border-emerald-500/40 bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-emerald-900/30 hover:bg-emerald-500"
        >
          <Plus className="h-4 w-4" />
          Add
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-left text-sm">
          <thead>
            <tr className="border-b border-white/5 text-xs uppercase tracking-wider text-slate-500">
              <th className="pb-3 pr-4">Coin</th>
              <th className="pb-3 pr-4 text-right">Price (USD)</th>
              <th className="pb-3 pr-4 text-right">24h</th>
              <th className="pb-3 pr-4 text-right hidden sm:table-cell">24h Volume</th>
              <th className="pb-3 text-right">Thao tác</th>
            </tr>
          </thead>
          <tbody>
            {watchlist.map((row) => {
              const ch = row.change_pct ?? row.change ?? 0;
              const up = ch >= 0;
              return (
                <tr key={row.symbol} className="border-b border-white/5 last:border-0">
                  <td className="py-3 pr-4">
                    <p className="font-mono font-bold text-white">
                      {row.symbol}
                      {row.is_custom ? (
                        <span className="ml-1.5 rounded bg-emerald-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-400">
                          custom
                        </span>
                      ) : null}
                    </p>
                    {row.name ? <p className="text-xs text-slate-500">{row.name}</p> : null}
                  </td>
                  <td className="py-3 pr-4 text-right">
                    <FlashPrice symbol={row.symbol} price={Number(row.price) || 0} className="font-mono text-slate-100">
                      {fmtUsd(row.price)}
                    </FlashPrice>
                  </td>
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
                    <div className="flex justify-end gap-1.5">
                      <button
                        type="button"
                        onClick={() => onBuy(row.symbol)}
                        className="rounded-lg border border-violet-500/40 bg-violet-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-violet-500"
                      >
                        Mua
                      </button>
                      <button
                        type="button"
                        onClick={() => onDetail(row.symbol)}
                        className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs font-semibold text-amber-200 hover:bg-amber-500/20"
                      >
                        Detail
                      </button>
                      {row.is_custom && onRemove ? (
                        <button
                          type="button"
                          onClick={() => onRemove(row.symbol)}
                          disabled={removingSymbol === row.symbol}
                          className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-1.5 text-rose-300 hover:bg-rose-500/20 disabled:opacity-50"
                          aria-label={`Remove ${row.symbol}`}
                        >
                          {removingSymbol === row.symbol ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <X className="h-3.5 w-3.5" />
                          )}
                        </button>
                      ) : null}
                    </div>
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
