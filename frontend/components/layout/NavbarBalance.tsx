'use client';

import { useQuery } from '@tanstack/react-query';
import { TrendingDown, TrendingUp, Wallet } from 'lucide-react';
import { getPaperWallet } from '../../lib/api';

function fmtUsd(v: number) {
  return `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtPct(v: number) {
  const sign = v >= 0 ? '+' : '';
  return `${sign}${v.toFixed(2)}%`;
}

export default function NavbarBalance() {
  const { data, isLoading } = useQuery({
    queryKey: ['paperWallet'],
    queryFn: getPaperWallet,
    refetchInterval: 3_000,
    staleTime: 2_000,
  });

  const equity = data?.total_equity_usd ?? 0;
  const cash = data?.cash_usd ?? 0;
  const pnlPct = data?.total_pnl_pct ?? 0;
  const up = pnlPct >= 0;

  return (
    <div className="flex items-center gap-2 rounded-xl border border-violet-500/30 bg-violet-950/40 px-3 py-2 sm:gap-3 sm:px-4">
      <Wallet className="hidden h-4 w-4 text-violet-300 sm:block" />
      <div className="text-right">
        <p className="text-[10px] font-medium uppercase tracking-wider text-slate-500">Balance</p>
        <p className="font-mono text-sm font-bold tabular-nums text-white sm:text-base">
          {isLoading ? '…' : fmtUsd(equity)}
        </p>
        {!isLoading ? (
          <p className="text-[10px] text-slate-500">
            Cash {fmtUsd(cash)}
          </p>
        ) : null}
      </div>
      {!isLoading && data ? (
        <span
          className={`inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 font-mono text-[10px] font-semibold tabular-nums sm:text-xs ${
            up ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'
          }`}
        >
          {up ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
          {fmtPct(pnlPct)}
        </span>
      ) : null}
    </div>
  );
}
