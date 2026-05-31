'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import { Loader2, Sparkles, TrendingDown, TrendingUp, X } from 'lucide-react';
import { useState } from 'react';
import { getAgentDebate, getCoinDetail, type DebateResponse } from '../../lib/api';
import AgentDebatePanel from '../agent/AgentDebatePanel';

function fmtUsd(v: number | null | undefined) {
  if (v == null || Number.isNaN(v) || v <= 0) return '—';
  if (v >= 1) return `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  return `$${v.toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 6 })}`;
}

function fmtPct(v: number | null | undefined) {
  if (v == null || Number.isNaN(v)) return '—';
  const sign = v >= 0 ? '+' : '';
  return `${sign}${v.toFixed(2)}%`;
}

function fmtLarge(v: number | null | undefined) {
  if (v == null || Number.isNaN(v)) return '—';
  if (v >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(2)}M`;
  return `$${v.toLocaleString('en-US')}`;
}

export default function CoinSymbolModal({
  symbol,
  onClose,
}: {
  readonly symbol: string;
  readonly onClose: () => void;
}) {
  const [showAiForm, setShowAiForm] = useState(false);
  const [holdingsInput, setHoldingsInput] = useState('0');
  const [submittedHoldings, setSubmittedHoldings] = useState<number | null>(null);
  const [debateResult, setDebateResult] = useState<DebateResponse | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['coinDetail', symbol],
    queryFn: () => getCoinDetail(symbol),
    staleTime: 15_000,
    refetchOnWindowFocus: false,
  });

  const debateMutation = useMutation({
    mutationFn: (holdings: number) => getAgentDebate(symbol, holdings),
    onSuccess: (result) => setDebateResult(result),
  });

  const prices = data?.prices;
  const changePct = data?.change_pct ?? 0;
  const up = changePct >= 0;

  const handleSubmitHoldings = () => {
    const parsed = Number.parseFloat(holdingsInput.replace(',', '.'));
    const holdings = Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
    setSubmittedHoldings(holdings);
    debateMutation.mutate(holdings);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 p-0 sm:items-center sm:p-4"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
      onKeyDown={(e) => {
        if (e.key === 'Escape') onClose();
      }}
    >
      <div
        className="flex max-h-[92vh] w-full max-w-2xl flex-col overflow-hidden rounded-t-3xl border border-white/10 bg-slate-950 shadow-2xl sm:rounded-3xl"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 border-b border-white/10 px-5 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-amber-300/90">Coin details</p>
            <h2 className="mt-1 font-mono text-2xl font-bold text-white">{symbol}</h2>
            {data?.name ? <p className="mt-0.5 text-sm text-slate-400">{data.name}</p> : null}
            {data?.rank ? <p className="text-xs text-slate-500">Market cap rank #{data.rank}</p> : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-white/10 bg-white/5 p-2 text-slate-300 hover:bg-white/10"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {isLoading ? (
            <div className="flex items-center justify-center gap-2 py-12 text-slate-400">
              <Loader2 className="h-5 w-5 animate-spin" />
              Loading CoinGecko data…
            </div>
          ) : isError || !data ? (
            <p className="py-8 text-center text-sm text-rose-300">Could not load data for {symbol}.</p>
          ) : (
            <div className="space-y-5">
              <div className="rounded-2xl border border-white/10 bg-gradient-to-br from-slate-900 to-slate-950 p-4">
                <div className="flex flex-wrap items-end justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-wider text-slate-500">Current price</p>
                    <p className="font-mono text-3xl font-bold tabular-nums text-white">{fmtUsd(prices?.last)}</p>
                  </div>
                  <span
                    className={`inline-flex items-center gap-1 rounded-lg px-3 py-1.5 font-mono text-lg font-bold tabular-nums ${
                      up ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'
                    }`}
                  >
                    {up ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
                    {fmtPct(changePct)}
                  </span>
                </div>
                {data.order_flow?.pressure_label ? (
                  <p className="mt-3 rounded-lg bg-slate-800/80 px-3 py-2 text-sm text-slate-300">
                    {data.order_flow.pressure_label}
                  </p>
                ) : null}
              </div>

              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {[
                  { label: '24h High', value: prices?.high_24h },
                  { label: '24h Low', value: prices?.low_24h },
                  { label: 'ATH', value: prices?.ath },
                  { label: 'ATL', value: prices?.atl },
                  { label: '24h Volume', value: data.volume_24h, fmt: fmtLarge },
                  { label: 'Market cap', value: data.market_cap, fmt: fmtLarge },
                ].map((row) => (
                  <div key={row.label} className="rounded-xl border border-white/5 bg-black/25 px-3 py-2.5">
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{row.label}</p>
                    <p className="mt-0.5 font-mono text-sm font-semibold text-slate-100">
                      {row.fmt ? row.fmt(row.value) : fmtUsd(row.value)}
                    </p>
                  </div>
                ))}
              </div>

              {data.volume_to_mcap_pct != null ? (
                <p className="text-xs text-slate-500">
                  Volume / market cap: {data.volume_to_mcap_pct}% · Circulating supply:{' '}
                  {data.circulating_supply?.toLocaleString('en-US') ?? '—'}
                </p>
              ) : null}

              {!showAiForm ? (
                <button
                  type="button"
                  onClick={() => setShowAiForm(true)}
                  className="flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-amber-600 to-orange-600 px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-amber-900/40 transition hover:from-amber-500 hover:to-orange-500"
                >
                  <Sparkles className="h-4 w-4" />
                  Run AI analysis
                </button>
              ) : (
                <div className="space-y-4 rounded-2xl border border-amber-500/25 bg-amber-950/15 p-4">
                  <div>
                    <p className="text-sm font-semibold text-amber-100">Your coin holdings</p>
                    <p className="mt-1 text-xs text-slate-400">
                      Enter how much {symbol} you hold (use 0 if you have none). The AI committee will debate based on this position.
                    </p>
                  </div>
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                    <label className="flex-1">
                      <span className="mb-1 block text-xs text-slate-500">Amount of {symbol}</span>
                      <input
                        type="number"
                        min={0}
                        step="any"
                        value={holdingsInput}
                        onChange={(e) => setHoldingsInput(e.target.value)}
                        className="w-full rounded-xl border border-white/10 bg-black/40 px-4 py-2.5 font-mono text-white outline-none ring-amber-500/30 focus:ring-2"
                        placeholder="0"
                      />
                    </label>
                    <button
                      type="button"
                      onClick={handleSubmitHoldings}
                      disabled={debateMutation.isPending}
                      className="flex items-center justify-center gap-2 rounded-xl bg-amber-500 px-6 py-2.5 text-sm font-semibold text-slate-950 hover:bg-amber-400 disabled:opacity-60"
                    >
                      {debateMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                      Submit
                    </button>
                  </div>

                  {submittedHoldings !== null ? (
                    <p className="text-xs text-slate-500">
                      Analyzing position: <span className="font-mono text-amber-200">{submittedHoldings}</span> {symbol}
                    </p>
                  ) : null}

                  <AgentDebatePanel
                    data={debateResult}
                    isLoading={debateMutation.isPending}
                    error={debateMutation.isError ? 'AI debate failed. Please try again.' : null}
                  />
                </div>
              )}
            </div>
          )}
        </div>

        {data?.quote_source ? (
          <p className="border-t border-white/5 px-5 py-2 text-[10px] text-slate-600">{data.quote_source}</p>
        ) : null}
      </div>
    </div>
  );
}
