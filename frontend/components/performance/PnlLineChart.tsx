'use client';

export type PnlPoint = {
  at: string;
  label: string;
  pnl_usd: number;
  pnl_pct: number;
};

type Props = {
  readonly title: string;
  readonly subtitle?: string;
  readonly data: PnlPoint[];
  readonly accent: 'emerald' | 'violet' | 'amber';
  readonly height?: number;
};

const ACCENTS = {
  emerald: { stroke: '#34d399', fill: 'rgba(52,211,153,0.12)', text: 'text-emerald-400' },
  violet: { stroke: '#a78bfa', fill: 'rgba(167,139,250,0.12)', text: 'text-violet-400' },
  amber: { stroke: '#fbbf24', fill: 'rgba(251,191,36,0.12)', text: 'text-amber-400' },
};

function fmtUsd(v: number) {
  const sign = v >= 0 ? '+' : '';
  return `${sign}$${Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function PnlLineChart({ title, subtitle, data, accent, height = 220 }: Props) {
  const colors = ACCENTS[accent];
  const w = 400;
  const h = height;
  const pad = { t: 16, r: 12, b: 28, l: 44 };
  const innerW = w - pad.l - pad.r;
  const innerH = h - pad.t - pad.b;

  const values = data.map((d) => d.pnl_pct);
  const minV = Math.min(0, ...values);
  const maxV = Math.max(0, ...values);
  const span = maxV - minV || 1;

  const points = data.map((d, i) => {
    const x = pad.l + (data.length <= 1 ? innerW / 2 : (i / (data.length - 1)) * innerW);
    const y = pad.t + innerH - ((d.pnl_pct - minV) / span) * innerH;
    return { x, y, ...d };
  });

  const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
  const areaPath =
    points.length > 0
      ? `${linePath} L ${points[points.length - 1].x} ${pad.t + innerH} L ${points[0].x} ${pad.t + innerH} Z`
      : '';

  const latest = data[data.length - 1];
  const zeroY = pad.t + innerH - ((0 - minV) / span) * innerH;

  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/80 p-4">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-bold text-white">{title}</h3>
          {subtitle ? <p className="text-[10px] text-slate-500">{subtitle}</p> : null}
        </div>
        {latest ? (
          <div className="text-right">
            <p className={`font-mono text-sm font-bold tabular-nums ${colors.text}`}>
              {latest.pnl_pct >= 0 ? '+' : ''}
              {latest.pnl_pct.toFixed(2)}%
            </p>
            <p className="font-mono text-[10px] text-slate-500">{fmtUsd(latest.pnl_usd)}</p>
          </div>
        ) : null}
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" role="img" aria-label={title}>
        <line
          x1={pad.l}
          y1={zeroY}
          x2={w - pad.r}
          y2={zeroY}
          stroke="rgba(255,255,255,0.08)"
          strokeDasharray="4 4"
        />
        {areaPath ? <path d={areaPath} fill={colors.fill} /> : null}
        {linePath ? (
          <path d={linePath} fill="none" stroke={colors.stroke} strokeWidth={2.5} strokeLinejoin="round" />
        ) : null}
        {points.map((p) => (
          <circle key={p.at} cx={p.x} cy={p.y} r={3} fill={colors.stroke} />
        ))}
        {points.map((p, i) =>
          i === 0 || i === points.length - 1 || i % Math.ceil(points.length / 4) === 0 ? (
            <text
              key={`${p.at}-lbl`}
              x={p.x}
              y={h - 6}
              textAnchor="middle"
              fill="#64748b"
              fontSize="9"
            >
              {p.label}
            </text>
          ) : null,
        )}
      </svg>
    </div>
  );
}
