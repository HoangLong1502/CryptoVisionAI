'use client';

import { useMutation } from '@tanstack/react-query';
import { Loader2, Plus, Search, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { addWatchlistCoin, searchCoins, type CoinSearchResult } from '../../lib/api';

export default function AddCoinModal({
  onClose,
  onAdded,
}: {
  readonly onClose: () => void;
  readonly onAdded: () => void;
}) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<CoinSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setResults([]);
      return;
    }
    const t = setTimeout(async () => {
      setSearching(true);
      try {
        const rows = await searchCoins(q);
        setResults(rows);
        setError(null);
      } catch {
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 350);
    return () => clearTimeout(t);
  }, [query]);

  const addMutation = useMutation({
    mutationFn: (opts: { symbol?: string; coinId?: string }) => addWatchlistCoin(opts),
    onSuccess: () => {
      onAdded();
      onClose();
    },
    onError: (e: Error) => setError(e.message),
  });

  const handleQuickAdd = () => {
    const sym = query.trim().toUpperCase();
    if (sym.length < 2) {
      setError('Nhập mã coin (ví dụ PEPE, ARB, WIF)');
      return;
    }
    setError(null);
    addMutation.mutate({ symbol: sym });
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
      onKeyDown={(e) => {
        if (e.key === 'Escape') onClose();
      }}
    >
      <div
        className="w-full max-w-lg rounded-2xl border border-white/10 bg-slate-950 p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between gap-2">
          <div>
            <h2 className="text-lg font-bold text-white">Thêm mã crypto</h2>
            <p className="mt-1 text-xs text-slate-500">Tìm trên CoinGecko · giá live Binance · đủ chức năng Mua/Detail/AI</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-white/10 bg-white/5 p-2 text-slate-300 hover:bg-white/10"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Mã hoặc tên: PEPE, Arbitrum, WIF…"
              className="w-full rounded-xl border border-white/10 bg-black/40 py-2.5 pl-10 pr-4 text-sm text-white outline-none ring-emerald-500/30 focus:ring-2"
              autoFocus
            />
          </div>
          <button
            type="button"
            onClick={handleQuickAdd}
            disabled={addMutation.isPending}
            className="flex items-center gap-1 rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-60"
          >
            {addMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Add
          </button>
        </div>

        {error ? <p className="mt-3 text-xs text-rose-400">{error}</p> : null}

        <div className="mt-4 max-h-64 overflow-y-auto rounded-xl border border-white/5 bg-black/20">
          {searching ? (
            <p className="flex items-center justify-center gap-2 py-8 text-sm text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              Đang tìm…
            </p>
          ) : results.length === 0 ? (
            <p className="py-8 text-center text-xs text-slate-600">
              {query.trim().length < 2 ? 'Gõ ít nhất 2 ký tự để tìm' : 'Không có kết quả'}
            </p>
          ) : (
            <ul className="divide-y divide-white/5">
              {results.map((row) => (
                <li key={`${row.coin_id}-${row.symbol}`}>
                  <button
                    type="button"
                    disabled={row.already_listed || addMutation.isPending}
                    onClick={() => addMutation.mutate({ coinId: row.coin_id })}
                    className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <div>
                      <p className="font-mono font-bold text-white">{row.symbol}</p>
                      <p className="text-xs text-slate-500">{row.name}</p>
                    </div>
                    <span className="text-xs text-slate-500">
                      {row.already_listed ? 'Đã có' : row.market_cap_rank ? `#${row.market_cap_rank}` : 'Add'}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
