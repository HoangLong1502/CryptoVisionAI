'use client';

import {
  AlertTriangle,
  CalendarClock,
  ChevronDown,
  ChevronUp,
  Clock,
  Droplets,
  LineChart,
  Sparkles,
  Target,
  TrendingDown,
  TrendingUp,
  Wallet,
} from 'lucide-react';
import { useState } from 'react';
import type { DebateResponse, TimingForecast } from '../../lib/api';

const TONE_STYLES: Record<string, string> = {
  positive: 'border-emerald-500/30 bg-emerald-950/40 text-emerald-100',
  warning: 'border-amber-500/35 bg-amber-950/40 text-amber-100',
  negative: 'border-rose-500/35 bg-rose-950/40 text-rose-100',
  neutral: 'border-slate-600/40 bg-slate-900/60 text-slate-200',
};

const VERDICT_BADGE: Record<string, string> = {
  positive: 'bg-emerald-500/20 text-emerald-200 ring-emerald-500/40',
  warning: 'bg-amber-500/20 text-amber-100 ring-amber-500/40',
  negative: 'bg-rose-500/20 text-rose-200 ring-rose-500/40',
  neutral: 'bg-slate-700/60 text-slate-200 ring-white/10',
};

function InsightIcon({ category, tone }: { readonly category: string; readonly tone: string }) {
  const cls = 'h-4 w-4 shrink-0';
  if (category === 'liquidity' || category === 'volume') return <Droplets className={cls} />;
  if (category === 'portfolio') return <Wallet className={cls} />;
  if (category === 'trend') return tone === 'warning' ? <TrendingDown className={cls} /> : <TrendingUp className={cls} />;
  if (category === 'alert') return <AlertTriangle className={cls} />;
  if (category === 'technical') return <LineChart className={cls} />;
  if (category === 'consensus') return <Sparkles className={cls} />;
  if (category === 'timing') return <CalendarClock className={cls} />;
  return <Sparkles className={cls} />;
}

function fmtPrice(v: number | undefined) {
  if (v == null || v <= 0) return '—';
  if (v >= 1) return `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  return `$${v.toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 6 })}`;
}

function TimingForecastPanel({ timing }: { readonly timing: TimingForecast }) {
  const confCls =
    timing.confidence === 'high'
      ? 'text-emerald-300'
      : timing.confidence === 'low'
        ? 'text-amber-300'
        : 'text-cyan-300';

  return (
    <div className="rounded-2xl border border-violet-500/25 bg-gradient-to-br from-violet-950/40 to-slate-950 p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-violet-300">
          <Clock className="h-4 w-4" />
          AI buy / sell timing
        </p>
        <span className={`text-[10px] font-semibold uppercase ${confCls}`}>
          {timing.confidence} confidence
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-950/20 p-3">
          <p className="flex items-center gap-1.5 text-xs font-semibold text-emerald-300">
            <TrendingUp className="h-3.5 w-3.5" />
            When to buy
          </p>
          <p className="mt-1 text-sm font-bold text-white">{timing.buy_window.label}</p>
          <p className="mt-0.5 font-mono text-[11px] text-slate-400">
            {timing.buy_window.start_date} → {timing.buy_window.end_date}
          </p>
          <div className="mt-2 space-y-1 text-xs text-slate-300">
            <p>
              Entry zone:{' '}
              <span className="font-mono text-emerald-200">
                {fmtPrice(timing.buy_window.entry_price_low)} – {fmtPrice(timing.buy_window.entry_price_high)}
              </span>
            </p>
            <p>
              Ideal entry:{' '}
              <span className="font-mono font-semibold text-emerald-100">
                {fmtPrice(timing.buy_window.entry_price_ideal)}
              </span>
            </p>
          </div>
          {timing.buy_window.recommended ? (
            <span className="mt-2 inline-block rounded-md bg-emerald-500/20 px-2 py-0.5 text-[10px] font-bold uppercase text-emerald-200">
              Buy window active
            </span>
          ) : null}
          <p className="mt-2 text-[11px] leading-snug text-slate-400">{timing.buy_window.note}</p>
        </div>

        <div className="rounded-xl border border-rose-500/20 bg-rose-950/20 p-3">
          <p className="flex items-center gap-1.5 text-xs font-semibold text-rose-300">
            <Target className="h-3.5 w-3.5" />
            When to sell & target price
          </p>
          <p className="mt-1 text-sm font-bold text-white">{timing.sell_window.label}</p>
          <p className="mt-0.5 font-mono text-[11px] text-slate-400">
            {timing.sell_window.start_date} → {timing.sell_window.end_date}
          </p>
          <div className="mt-2 space-y-1 text-xs text-slate-300">
            <p>
              Target price:{' '}
              <span className="font-mono font-semibold text-rose-100">
                {fmtPrice(timing.sell_window.target_price_base)}
              </span>
            </p>
            <p>
              Sell range:{' '}
              <span className="font-mono text-rose-200">
                {fmtPrice(timing.sell_window.target_price_low)} – {fmtPrice(timing.sell_window.target_price_high)}
              </span>
            </p>
            <p>
              Stop-loss:{' '}
              <span className="font-mono text-amber-200">{fmtPrice(timing.sell_window.stop_loss)}</span>
              {' · '}
              Est. gain{' '}
              <span
                className={
                  timing.sell_window.expected_gain_pct >= 0 ? 'text-emerald-300' : 'text-rose-300'
                }
              >
                {timing.sell_window.expected_gain_pct >= 0 ? '+' : ''}
                {timing.sell_window.expected_gain_pct.toFixed(1)}%
              </span>
            </p>
          </div>
          <p className="mt-2 text-[11px] leading-snug text-slate-400">{timing.sell_window.note}</p>
        </div>
      </div>

      {timing.disclaimer ? (
        <p className="mt-3 text-[10px] leading-snug text-slate-500">{timing.disclaimer}</p>
      ) : null}
    </div>
  );
}

function VoteBar({ votes }: { readonly votes: { buy: number; hold: number; sell: number } }) {
  const total = votes.buy + votes.hold + votes.sell || 1;
  const buyW = (votes.buy / total) * 100;
  const holdW = (votes.hold / total) * 100;
  const sellW = (votes.sell / total) * 100;
  return (
    <div className="space-y-2">
      <div className="flex h-2.5 overflow-hidden rounded-full bg-slate-800">
        {buyW > 0 ? <div className="bg-emerald-500" style={{ width: `${buyW}%` }} title="Buy" /> : null}
        {holdW > 0 ? <div className="bg-slate-500" style={{ width: `${holdW}%` }} title="Hold" /> : null}
        {sellW > 0 ? <div className="bg-rose-500" style={{ width: `${sellW}%` }} title="Sell" /> : null}
      </div>
      <p className="text-xs text-slate-400">
        <span className="text-emerald-400">{votes.buy} buy</span>
        {' · '}
        <span className="text-slate-300">{votes.hold} hold</span>
        {' · '}
        <span className="text-rose-400">{votes.sell} sell</span>
      </p>
    </div>
  );
}

export default function AgentDebatePanel({
  data,
  isLoading,
  error,
}: {
  readonly data?: DebateResponse | null;
  readonly isLoading: boolean;
  readonly error?: string | null;
}) {
  const [showAgents, setShowAgents] = useState(false);
  const brief = data?.user_brief;
  const debate = data?.debate ?? [];
  const votes = brief?.votes ?? data?.consensus?.agent_votes ?? { buy: 0, hold: 0, sell: 0 };

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-amber-500/20 bg-amber-950/20 px-4 py-6 text-center text-sm text-slate-300">
        <Sparkles className="mx-auto mb-2 h-6 w-6 animate-pulse text-amber-400" />
        Crypto committee in session…
        <p className="mt-2 text-xs text-slate-500">5 agents + Portfolio Advisor + Chair — ~30–60 seconds</p>
      </div>
    );
  }

  if (error) {
    return <p className="rounded-xl border border-rose-500/30 bg-rose-950/30 px-4 py-3 text-sm text-rose-200">{error}</p>;
  }

  if (!brief) {
    return <p className="text-sm text-slate-400">No analysis results yet.</p>;
  }

  return (
    <div className="space-y-4">
      {data?.workflow ? (
        <div className="rounded-xl border border-white/5 bg-black/20 px-3 py-2 text-xs text-slate-500">
          {data.workflow.title}
        </div>
      ) : null}

      <div className="rounded-2xl border border-white/10 bg-gradient-to-br from-slate-900 to-slate-950 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-amber-300">Committee verdict</p>
            <h3 className="mt-1 text-xl font-bold text-white">{brief.headline}</h3>
          </div>
          <span
            className={`rounded-xl px-3 py-1.5 text-sm font-semibold ring-1 ${VERDICT_BADGE[brief.verdict_tone] ?? VERDICT_BADGE.neutral}`}
          >
            {brief.verdict_label}
          </span>
        </div>
        <p className="mt-3 text-sm leading-relaxed text-slate-300">{brief.summary}</p>
        <VoteBar votes={votes} />
        <div className="mt-4 rounded-xl border border-cyan-500/25 bg-cyan-950/25 px-3 py-2.5 text-sm text-cyan-100">
          <span className="font-semibold">Suggested action: </span>
          {brief.action}
        </div>
      </div>

      {brief.timing_forecast ? <TimingForecastPanel timing={brief.timing_forecast} /> : null}

      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Key takeaways</p>
        {brief.insights
          .filter((item) => item.category !== 'timing')
          .map((item, idx) => (
          <div
            key={`${item.category}-${idx}`}
            className={`flex gap-3 rounded-xl border p-3 ${TONE_STYLES[item.tone] ?? TONE_STYLES.neutral}`}
          >
            <InsightIcon category={item.category} tone={item.tone} />
            <div className="min-w-0">
              <p className="font-semibold">{item.title}</p>
              <p className="mt-1 text-sm leading-snug opacity-90">{item.text}</p>
            </div>
          </div>
        ))}
      </div>

      {brief.agent_lines && brief.agent_lines.length > 0 ? (
        <div className="rounded-xl border border-white/5 bg-black/20 p-3">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">Agent summaries</p>
          <ul className="space-y-2">
            {brief.agent_lines.map((line) => (
              <li key={line.agent} className="flex gap-2 text-sm">
                <span
                  className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${
                    line.verdict_label === 'Buy'
                      ? 'bg-emerald-500/25 text-emerald-200'
                      : line.verdict_label === 'Sell'
                        ? 'bg-rose-500/25 text-rose-200'
                        : 'bg-slate-600/50 text-slate-200'
                  }`}
                >
                  {line.verdict_label}
                </span>
                <span className="text-slate-300">
                  <span className="font-medium text-slate-200">{line.agent_label}:</span> {line.one_liner}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <button
        type="button"
        onClick={() => setShowAgents((v) => !v)}
        className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/10 py-2 text-xs text-slate-400 hover:bg-white/5"
      >
        {showAgents ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        {showAgents ? 'Hide agent debate details' : 'Show agent debate details'}
      </button>

      {showAgents
        ? debate.map((item) => (
            <div key={item.agent} className="rounded-2xl border border-slate-800 bg-slate-950/80 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-wider text-slate-500">{item.agent}</p>
                  <p className="mt-1 text-lg font-semibold capitalize">{item.verdict}</p>
                  <p className="mt-1 text-sm text-slate-400">{item.rationale}</p>
                </div>
                <span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-300">
                  {Math.round(item.confidence)}%
                </span>
              </div>
            </div>
          ))
        : null}
    </div>
  );
}
