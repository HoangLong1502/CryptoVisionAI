'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useQueryClient } from '@tanstack/react-query';
import { Bot, ChartLine, Loader2, RefreshCw, RotateCcw, TrendingDown, TrendingUp, Wallet } from 'lucide-react';
import {
  getAutoTradingStatus,
  getPaperWallet,
  paperBuy,
  paperReset,
  paperSell,
  toggleAutoTrading,
  type AutoTradingStatus,
  type PaperHolding,
  type PaperWalletSnapshot,
} from '../../lib/api';

export type { PaperWalletSnapshot };

const REFRESH_MS = 200;

function fmtUsd(v: number) {
  return `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtPct(v: number) {
  const sign = v >= 0 ? '+' : '';
  return `${sign}${v.toFixed(2)}%`;
}

function PnlBadge({ value, className = '' }: { readonly value: number; readonly className?: string }) {
  const up = value >= 0;
  return (
    <span
      className={`inline-flex items-center gap-0.5 font-mono text-xs font-semibold tabular-nums ${
        up ? 'text-emerald-400' : 'text-rose-400'
      } ${className}`}
    >
      {up ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
      {fmtPct(value)}
    </span>
  );
}

function HoldingRow({
  row,
  onSell,
  selling,
}: {
  readonly row: PaperHolding;
  readonly onSell: (symbol: string, sellAll: boolean) => void;
  readonly selling: string | null;
}) {
  const busy = selling === row.symbol;
  return (
    <tr className="border-b border-white/5 last:border-0">
      <td className="py-2.5 pr-3 font-mono font-bold text-white">{row.symbol}</td>
      <td className="py-2.5 pr-3 text-right font-mono text-xs text-slate-300">{row.quantity.toFixed(6)}</td>
      <td className="py-2.5 pr-3 text-right font-mono text-xs text-slate-400">{fmtUsd(row.current_price)}</td>
      <td className="py-2.5 pr-3 text-right font-mono text-xs text-slate-200">{fmtUsd(row.value_usd)}</td>
      <td className="py-2.5 pr-3 text-right">
        <PnlBadge value={row.pnl_pct} />
        <p className="mt-0.5 font-mono text-[10px] text-slate-500">
          {row.pnl_usd >= 0 ? '+' : ''}
          {fmtUsd(row.pnl_usd)}
        </p>
      </td>
      <td className="py-2.5 pr-3 text-right">
        <PnlBadge value={row.change_24h_pct} />
      </td>
      <td className="py-2.5 text-right">
        <button
          type="button"
          disabled={busy}
          onClick={() => onSell(row.symbol, true)}
          className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-2 py-1 text-[10px] font-semibold text-rose-200 hover:bg-rose-500/20 disabled:opacity-50"
        >
          {busy ? <Loader2 className="inline h-3 w-3 animate-spin" /> : 'Bán hết'}
        </button>
      </td>
    </tr>
  );
}

export default function PaperWallet({ onWalletChange }: { readonly onWalletChange?: () => void }) {
  const queryClient = useQueryClient();
  const [wallet, setWallet] = useState<PaperWalletSnapshot | null>(null);
  const [autoTrading, setAutoTrading] = useState<AutoTradingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selling, setSelling] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);
  const [togglingAuto, setTogglingAuto] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [data, auto] = await Promise.all([getPaperWallet(), getAutoTradingStatus()]);
      setWallet(data);
      setAutoTrading(auto);
      setError(null);
    } catch {
      setError('Không tải được ví ảo');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, REFRESH_MS);
    return () => clearInterval(t);
  }, [refresh]);

  const handleSell = async (symbol: string, sellAll: boolean) => {
    setSelling(symbol);
    setError(null);
    try {
      const res = await paperSell(symbol, { sellAll });
      setWallet(res.wallet);
      queryClient.invalidateQueries({ queryKey: ['paperWallet'] });
      onWalletChange?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Bán thất bại');
    } finally {
      setSelling(null);
    }
  };

  const handleToggleAuto = async () => {
    setTogglingAuto(true);
    setError(null);
    try {
      const res = await toggleAutoTrading();
      setAutoTrading(res);
      const walletData = await getPaperWallet();
      setWallet(walletData);
      queryClient.invalidateQueries({ queryKey: ['paperWallet'] });
      onWalletChange?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Auto-trading thất bại');
    } finally {
      setTogglingAuto(false);
    }
  };

  const handleReset = async () => {
    if (!globalThis.confirm('Reset ví ảo về $1,000 và xóa toàn bộ coin đang giữ?')) return;
    setResetting(true);
    setError(null);
    try {
      const res = await paperReset();
      setWallet(res.wallet);
      queryClient.invalidateQueries({ queryKey: ['paperWallet'] });
      onWalletChange?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Reset thất bại');
    } finally {
      setResetting(false);
    }
  };

  if (loading && !wallet) {
    return (
      <section className="section-card mb-6 flex items-center justify-center gap-2 py-10 text-slate-400">
        <Loader2 className="h-5 w-5 animate-spin" />
        Đang tải ví tiền ảo…
      </section>
    );
  }

  const w = wallet!;
  const totalUp = w.total_pnl_pct >= 0;
  const autoOn = autoTrading?.enabled === true;

  return (
    <section className="section-card mb-6">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-violet-500/20 text-violet-300">
            <Wallet className="h-5 w-5" />
          </span>
          <div>
            <h2 className="text-lg font-bold text-white">Ví tiền ảo (Paper)</h2>
            <p className="text-xs text-slate-500">$1,000 USDT ban đầu · giá live từ Binance</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href="/performance"
            className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-slate-300 hover:bg-white/10"
          >
            <ChartLine className="h-4 w-4" />
            Charts
          </Link>
          <button
            type="button"
            onClick={handleToggleAuto}
            disabled={togglingAuto}
            className={`flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition disabled:opacity-60 ${
              autoOn
                ? 'border border-emerald-400/50 bg-emerald-600 text-white shadow-lg shadow-emerald-900/40 ring-2 ring-emerald-400/30'
                : 'border border-white/10 bg-slate-800 text-slate-300 hover:bg-slate-700'
            }`}
          >
            {togglingAuto ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Bot className={`h-4 w-4 ${autoOn ? 'animate-pulse' : ''}`} />
            )}
            {autoOn ? 'Auto Trading ON' : 'Auto Trading'}
          </button>
          <button
            type="button"
            onClick={() => refresh()}
            className="rounded-lg border border-white/10 bg-white/5 p-2 text-slate-400 hover:text-white"
            aria-label="Refresh"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={handleReset}
            disabled={resetting}
            className="flex items-center gap-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-400 hover:text-white disabled:opacity-50"
          >
            {resetting ? <Loader2 className="h-3 w-3 animate-spin" /> : <RotateCcw className="h-3 w-3" />}
            Reset
          </button>
        </div>
      </div>

      {autoOn && autoTrading ? (
        <div className="mb-4 rounded-xl border border-emerald-500/25 bg-emerald-950/25 px-4 py-3 text-xs text-emerald-100">
          <p className="font-semibold text-emerald-300">
            Bot đang chạy — tự mua/bán theo AI committee
          </p>
          <p className="mt-1 text-slate-400">
            Tối đa {Math.round((autoTrading.settings.max_deploy_pct ?? 0.8) * 100)}% vốn · stop-loss -
            {autoTrading.settings.stop_loss_pct ?? 5}% · entry ≥ {autoTrading.settings.min_buy_score ?? 70}/100
            {autoTrading.risk ? (
              <>
                {' '}
                · drawdown {autoTrading.risk.drawdown_pct.toFixed(1)}% (max{' '}
                {autoTrading.settings.max_drawdown_pct ?? 10}%)
              </>
            ) : null}
          </p>
          {autoTrading.last_error ? (
            <p className="mt-1 text-rose-400">Lỗi gần nhất: {autoTrading.last_error}</p>
          ) : null}
        </div>
      ) : null}

      {autoTrading?.risk_halted ? (
        <div className="mb-4 rounded-xl border border-rose-500/40 bg-rose-950/30 px-4 py-3 text-xs text-rose-100">
          <p className="font-semibold text-rose-300">Bot đã dừng khẩn cấp (circuit breaker)</p>
          <p className="mt-1 text-slate-400">{autoTrading.risk_halt_reason}</p>
          <p className="mt-1 text-slate-500">Reset ví hoặc chờ tài khoản hồi phục dưới ngưỡng drawdown rồi bật lại.</p>
        </div>
      ) : null}

      {autoTrading && autoTrading.recent_actions.length > 0 ? (
        <div className="mb-4 rounded-xl border border-white/5 bg-black/20 px-4 py-3">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            Lệnh auto gần đây
          </p>
          <ul className="space-y-1.5">
            {autoTrading.recent_actions.slice(0, 5).map((act, i) => (
              <li key={`${act.at}-${act.symbol}-${i}`} className="flex flex-wrap items-center gap-2 text-xs">
                <span
                  className={`rounded px-1.5 py-0.5 font-mono font-bold uppercase ${
                    act.side === 'buy' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
                  }`}
                >
                  {act.side}
                </span>
                <span className="font-mono font-semibold text-white">{act.symbol}</span>
                {act.amount_usd != null ? (
                  <span className="font-mono text-slate-400">${act.amount_usd.toFixed(2)}</span>
                ) : null}
                {act.ai_confidence != null ? (
                  <span className="text-slate-600">{act.ai_confidence}% AI</span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {error ? <p className="mb-3 rounded-lg bg-rose-950/40 px-3 py-2 text-xs text-rose-300">{error}</p> : null}

      <div className="mb-4 grid gap-3 sm:grid-cols-4">
        <div className="rounded-2xl border border-white/5 bg-black/25 px-4 py-3">
          <p className="text-[10px] uppercase tracking-wider text-slate-500">Tiền mặt</p>
          <p className="mt-1 font-mono text-xl font-bold text-white">{fmtUsd(w.cash_usd)}</p>
        </div>
        <div className="rounded-2xl border border-white/5 bg-black/25 px-4 py-3">
          <p className="text-[10px] uppercase tracking-wider text-slate-500">Giá trị coin</p>
          <p className="mt-1 font-mono text-xl font-bold text-white">{fmtUsd(w.holdings_value_usd)}</p>
        </div>
        <div className="rounded-2xl border border-white/5 bg-black/25 px-4 py-3">
          <p className="text-[10px] uppercase tracking-wider text-slate-500">Tổng tài sản</p>
          <p className="mt-1 font-mono text-xl font-bold text-amber-200">{fmtUsd(w.total_equity_usd)}</p>
        </div>
        <div className="rounded-2xl border border-white/5 bg-black/25 px-4 py-3">
          <p className="text-[10px] uppercase tracking-wider text-slate-500">Lãi / lỗ tổng</p>
          <p className={`mt-1 font-mono text-xl font-bold ${totalUp ? 'text-emerald-400' : 'text-rose-400'}`}>
            {w.total_pnl_usd >= 0 ? '+' : ''}
            {fmtUsd(w.total_pnl_usd)}
          </p>
          <PnlBadge value={w.total_pnl_pct} className="mt-1" />
        </div>
      </div>

      {w.holdings.length === 0 ? (
        <p className="rounded-xl border border-dashed border-white/10 bg-black/20 px-4 py-6 text-center text-sm text-slate-500">
          Chưa có coin nào. Bấm <span className="text-violet-300">Mua</span> trên bảng giá bên dưới để thử.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-white/5 text-[10px] uppercase tracking-wider text-slate-500">
                <th className="pb-2 pr-3">Coin</th>
                <th className="pb-2 pr-3 text-right">Số lượng</th>
                <th className="pb-2 pr-3 text-right">Giá hiện tại</th>
                <th className="pb-2 pr-3 text-right">Giá trị</th>
                <th className="pb-2 pr-3 text-right">Lãi/lỗ</th>
                <th className="pb-2 pr-3 text-right">24h</th>
                <th className="pb-2 text-right" />
              </tr>
            </thead>
            <tbody>
              {w.holdings.map((row) => (
                <HoldingRow key={row.symbol} row={row} onSell={handleSell} selling={selling} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

/** Quick buy panel — used inside coin detail modal */
export function PaperBuyPanel({
  symbol,
  livePrice,
  cashUsd,
  onSuccess,
}: {
  readonly symbol: string;
  readonly livePrice?: number;
  readonly cashUsd?: number;
  readonly onSuccess?: (wallet: PaperWalletSnapshot) => void;
}) {
  const queryClient = useQueryClient();
  const [amount, setAmount] = useState('100');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const presets = [50, 100, 500, 1000];

  const handleBuy = async () => {
    const usd = Number.parseFloat(amount.replace(',', '.'));
    if (!Number.isFinite(usd) || usd < 1) {
      setErr('Nhập số tiền tối thiểu $1');
      return;
    }
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await paperBuy(symbol, usd);
      setMsg(res.message);
      queryClient.invalidateQueries({ queryKey: ['paperWallet'] });
      onSuccess?.(res.wallet);
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Mua thất bại');
    } finally {
      setBusy(false);
    }
  };

  const estQty = livePrice && livePrice > 0 ? Number.parseFloat(amount || '0') / livePrice : null;

  return (
    <div className="rounded-2xl border border-violet-500/25 bg-violet-950/20 p-4">
      <p className="text-sm font-semibold text-violet-100">Mua thử bằng tiền ảo</p>
      <p className="mt-1 text-xs text-slate-400">
        Số dư khả dụng:{' '}
        <span className="font-mono text-violet-200">{cashUsd != null ? fmtUsd(cashUsd) : '…'}</span>
        {livePrice ? (
          <>
            {' '}
            · Giá {symbol}: <span className="font-mono text-white">{fmtUsd(livePrice)}</span>
          </>
        ) : null}
      </p>

      <div className="mt-3 flex flex-wrap gap-2">
        {presets.map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => setAmount(String(p))}
            className="rounded-lg border border-white/10 bg-black/30 px-3 py-1 text-xs font-mono text-slate-300 hover:border-violet-500/40"
          >
            ${p}
          </button>
        ))}
      </div>

      <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end">
        <label className="flex-1">
          <span className="mb-1 block text-xs text-slate-500">Số tiền USD</span>
          <input
            type="number"
            min={1}
            step="any"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="w-full rounded-xl border border-white/10 bg-black/40 px-4 py-2.5 font-mono text-white outline-none ring-violet-500/30 focus:ring-2"
          />
        </label>
        <button
          type="button"
          onClick={handleBuy}
          disabled={busy}
          className="flex items-center justify-center gap-2 rounded-xl bg-violet-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-violet-500 disabled:opacity-60"
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Mua {symbol}
        </button>
      </div>

      {estQty != null && estQty > 0 ? (
        <p className="mt-2 text-xs text-slate-500">
          Ước tính nhận: <span className="font-mono text-slate-300">{estQty.toFixed(8)} {symbol}</span>
        </p>
      ) : null}
      {msg ? <p className="mt-2 text-xs text-emerald-400">{msg}</p> : null}
      {err ? <p className="mt-2 text-xs text-rose-400">{err}</p> : null}
    </div>
  );
}
