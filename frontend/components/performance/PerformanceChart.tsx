'use client';

export type PnlPoint = {
  at: string;
  label: string;
  pnl_usd: number;
  pnl_pct: number;
};

export type ChartMode = 'line' | 'pie' | 'candle';

type Accent = 'emerald' | 'violet' | 'amber';

type Props = {
  readonly title: string;
  readonly subtitle?: string;
  readonly data: PnlPoint[];
  readonly accent: Accent;
  readonly mode: ChartMode;
  readonly height?: number;
};

const ACCENTS: Record<
  Accent,
  { stroke: string; fill: string; text: string; up: string; down: string }
> = {
  emerald: {
    stroke: '#34d399',
    fill: 'rgba(52,211,153,0.12)',
    text: 'text-emerald-400',
    up: '#34d399',
    down: '#f87171',
  },
  violet: {
    stroke: '#a78bfa',
    fill: 'rgba(167,139,250,0.12)',
    text: 'text-violet-400',
    up: '#a78bfa',
    down: '#f87171',
  },
  amber: {
    stroke: '#fbbf24',
    fill: 'rgba(251,191,36,0.12)',
    text: 'text-amber-400',
    up: '#fbbf24',
    down: '#f87171',
  },
};

function fmtUsd(v: number) {
  const sign = v >= 0 ? '+' : '';
  return `${sign}$${Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtPct(v: number) {
  const sign = v >= 0 ? '+' : '';
  return `${sign}${v.toFixed(1)}%`;
}

function niceTicks(minV: number, maxV: number, count = 5): number[] {
  const span = maxV - minV || 1;
  const out: number[] = [];
  for (let i = 0; i < count; i++) {
    out.push(minV + (span * i) / (count - 1));
  }
  return out;
}

type Candle = PnlPoint & { open: number; close: number; high: number; low: number };

function toCandles(data: PnlPoint[]): Candle[] {
  return data.map((d, i) => {
    const open = i > 0 ? data[i - 1].pnl_pct : 0;
    const close = d.pnl_pct;
    return {
      ...d,
      open,
      close,
      high: Math.max(open, close),
      low: Math.min(open, close),
    };
  });
}

function pieSlices(data: PnlPoint[]) {
  let gain = 0;
  let loss = 0;
  for (let i = 1; i < data.length; i++) {
    const delta = data[i].pnl_pct - data[i - 1].pnl_pct;
    if (delta >= 0) gain += delta;
    else loss += Math.abs(delta);
  }
  if (gain === 0 && loss === 0) {
    const last = data[data.length - 1]?.pnl_pct ?? 0;
    if (last >= 0) gain = Math.abs(last) || 1;
    else loss = Math.abs(last) || 1;
  }
  return [
    { label: 'Tăng', value: gain, color: '#34d399' },
    { label: 'Giảm', value: loss, color: '#f87171' },
  ].filter((s) => s.value > 0.001);
}

function YAxisGrid({
  w,
  pad,
  minV,
  span,
  innerH,
}: {
  readonly w: number;
  readonly pad: { t: number; r: number; b: number; l: number };
  readonly minV: number;
  readonly span: number;
  readonly innerH: number;
}) {
  const ticks = niceTicks(minV, minV + span, 5);
  return (
    <>
      {ticks.map((tick) => {
        const y = pad.t + innerH - ((tick - minV) / span) * innerH;
        return (
          <g key={tick}>
            <line x1={pad.l} y1={y} x2={w - pad.r} y2={y} stroke="rgba(255,255,255,0.06)" strokeWidth={1} />
            <text x={pad.l - 6} y={y + 3} textAnchor="end" fill="#94a3b8" fontSize="9" fontFamily="monospace">
              {fmtPct(tick)}
            </text>
          </g>
        );
      })}
      <text
        x={10}
        y={pad.t + innerH / 2}
        textAnchor="middle"
        fill="#64748b"
        fontSize="8"
        transform={`rotate(-90 10 ${pad.t + innerH / 2})`}
      >
        % PnL
      </text>
    </>
  );
}

function LineChartBody({
  points,
  colors,
  pad,
  innerH,
  w,
  h,
  minV,
  span,
}: {
  readonly points: Array<PnlPoint & { x: number; y: number }>;
  readonly colors: (typeof ACCENTS)[Accent];
  readonly pad: { t: number; r: number; b: number; l: number };
  readonly innerH: number;
  readonly w: number;
  readonly h: number;
  readonly minV: number;
  readonly span: number;
}) {
  const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
  const areaPath =
    points.length > 0
      ? `${linePath} L ${points[points.length - 1].x} ${pad.t + innerH} L ${points[0].x} ${pad.t + innerH} Z`
      : '';
  const zeroY = pad.t + innerH - ((0 - minV) / span) * innerH;

  return (
    <>
      <line x1={pad.l} y1={zeroY} x2={w - pad.r} y2={zeroY} stroke="rgba(255,255,255,0.12)" strokeWidth={1} />
      {areaPath ? <path d={areaPath} fill={colors.fill} /> : null}
      {linePath ? (
        <path d={linePath} fill="none" stroke={colors.stroke} strokeWidth={2.5} strokeLinejoin="round" />
      ) : null}
      {points.map((p) => (
        <circle key={p.at} cx={p.x} cy={p.y} r={3} fill={colors.stroke} />
      ))}
      {points.map((p, i) =>
        i === 0 || i === points.length - 1 || i % Math.max(1, Math.ceil(points.length / 4)) === 0 ? (
          <text key={`${p.at}-x`} x={p.x} y={h - 6} textAnchor="middle" fill="#64748b" fontSize="9">
            {p.label}
          </text>
        ) : null,
      )}
    </>
  );
}

function CandleChartBody({
  candles,
  pad,
  innerW,
  innerH,
  minV,
  span,
  colors,
}: {
  readonly candles: Candle[];
  readonly pad: { t: number; r: number; b: number; l: number };
  readonly innerW: number;
  readonly innerH: number;
  readonly minV: number;
  readonly span: number;
  readonly colors: (typeof ACCENTS)[Accent];
}) {
  const slot = candles.length > 0 ? innerW / candles.length : innerW;
  const bodyW = Math.max(4, Math.min(14, slot * 0.55));
  const yOf = (v: number) => pad.t + innerH - ((v - minV) / span) * innerH;

  return (
    <>
      {candles.map((c, i) => {
        const cx = pad.l + slot * i + slot / 2;
        const yOpen = yOf(c.open);
        const yClose = yOf(c.close);
        const yHigh = yOf(c.high);
        const yLow = yOf(c.low);
        const up = c.close >= c.open;
        const fill = up ? colors.up : colors.down;
        const top = Math.min(yOpen, yClose);
        const bodyH = Math.max(2, Math.abs(yClose - yOpen));

        return (
          <g key={c.at}>
            <line x1={cx} y1={yHigh} x2={cx} y2={yLow} stroke={fill} strokeWidth={1.5} />
            <rect x={cx - bodyW / 2} y={top} width={bodyW} height={bodyH} fill={fill} rx={1} opacity={0.9} />
            {i === 0 || i === candles.length - 1 || i % Math.max(1, Math.ceil(candles.length / 4)) === 0 ? (
              <text x={cx} y={pad.t + innerH + 18} textAnchor="middle" fill="#64748b" fontSize="8">
                {c.label}
              </text>
            ) : null}
          </g>
        );
      })}
    </>
  );
}

function PieChartBody({
  slices,
  cx,
  cy,
  r,
}: {
  readonly slices: Array<{ label: string; value: number; color: string }>;
  readonly cx: number;
  readonly cy: number;
  readonly r: number;
}) {
  const total = slices.reduce((s, x) => s + x.value, 0) || 1;
  let angle = -Math.PI / 2;

  return (
    <>
      {slices.map((slice) => {
        const sweep = (slice.value / total) * Math.PI * 2;
        const x1 = cx + r * Math.cos(angle);
        const y1 = cy + r * Math.sin(angle);
        angle += sweep;
        const x2 = cx + r * Math.cos(angle);
        const y2 = cy + r * Math.sin(angle);
        const large = sweep > Math.PI ? 1 : 0;
        const d = `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2} Z`;
        const pct = (slice.value / total) * 100;
        return (
          <g key={slice.label}>
            <path d={d} fill={slice.color} opacity={0.88} stroke="#0f172a" strokeWidth={1} />
            <title>{`${slice.label}: ${pct.toFixed(1)}%`}</title>
          </g>
        );
      })}
      <circle cx={cx} cy={cy} r={r * 0.45} fill="#0f172a" />
      {slices.map((slice, i) => {
        const pct = (slice.value / total) * 100;
        return (
          <text key={`${slice.label}-legend`} x={cx + r + 16} y={cy - r / 2 + i * 18} fill="#cbd5e1" fontSize="10">
            <tspan fill={slice.color}>● </tspan>
            {slice.label} {pct.toFixed(1)}%
          </text>
        );
      })}
    </>
  );
}

export default function PerformanceChart({ title, subtitle, data, accent, mode, height = 240 }: Props) {
  const colors = ACCENTS[accent];
  const w = 420;
  const h = height;
  const pad = { t: 20, r: mode === 'pie' ? 88 : 16, b: 32, l: 56 };
  const innerW = w - pad.l - pad.r;
  const innerH = h - pad.t - pad.b;

  const values = data.map((d) => d.pnl_pct);
  const candleVals = toCandles(data).flatMap((c) => [c.open, c.close, c.high, c.low]);
  const allVals = mode === 'candle' ? candleVals : values;
  const minV = Math.min(0, ...allVals, -0.5);
  const maxV = Math.max(0, ...allVals, 0.5);
  const span = maxV - minV || 1;

  const points = data.map((d, i) => {
    const x = pad.l + (data.length <= 1 ? innerW / 2 : (i / (data.length - 1)) * innerW);
    const y = pad.t + innerH - ((d.pnl_pct - minV) / span) * innerH;
    return { x, y, ...d };
  });

  const latest = data[data.length - 1];
  const slices = pieSlices(data);

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
        {mode === 'pie' ? (
          <PieChartBody slices={slices} cx={pad.l + innerW * 0.38} cy={pad.t + innerH / 2} r={Math.min(innerW, innerH) * 0.32} />
        ) : (
          <>
            <YAxisGrid w={w} pad={pad} minV={minV} span={span} innerH={innerH} />
            {mode === 'line' ? (
              <LineChartBody points={points} colors={colors} pad={pad} innerH={innerH} w={w} h={h} minV={minV} span={span} />
            ) : (
              <CandleChartBody candles={toCandles(data)} pad={pad} innerW={innerW} innerH={innerH} minV={minV} span={span} colors={colors} />
            )}
          </>
        )}
      </svg>
      {mode === 'candle' ? (
        <p className="mt-1 text-center text-[9px] text-slate-600">Nến xanh = kỳ tăng · Nến đỏ = kỳ giảm (% PnL)</p>
      ) : null}
    </div>
  );
}

export function ChartModeSwitcher({
  mode,
  onChange,
}: {
  readonly mode: ChartMode;
  readonly onChange: (m: ChartMode) => void;
}) {
  const items: { id: ChartMode; label: string }[] = [
    { id: 'line', label: 'Đường' },
    { id: 'candle', label: 'Nến' },
    { id: 'pie', label: 'Tròn' },
  ];
  return (
    <div className="flex rounded-xl border border-white/10 bg-black/30 p-1">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onChange(item.id)}
          className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
            mode === item.id ? 'bg-amber-500/20 text-amber-200' : 'text-slate-400 hover:text-white'
          }`}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
