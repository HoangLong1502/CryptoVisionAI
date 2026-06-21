'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { ArrowLeft, Loader2 } from 'lucide-react';
import PerformanceChart, { ChartModeSwitcher, type ChartMode } from '../../../components/performance/PerformanceChart';
import { getPerformanceMonth, type PerformanceChartData } from '../../../lib/api';

export default function PerformanceMonthPage() {
  const [data, setData] = useState<PerformanceChartData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chartMode, setChartMode] = useState<ChartMode>('line');

  useEffect(() => {
    getPerformanceMonth()
      .then(setData)
      .catch(() => setError('Không tải được dữ liệu biểu đồ'))
      .finally(() => setLoading(false));
    const t = setInterval(() => {
      getPerformanceMonth().then(setData).catch(() => {});
    }, 60_000);
    return () => clearInterval(t);
  }, []);

  return (
    <main className="mx-auto max-w-6xl px-4 py-6">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link
            href="/performance"
            className="mb-2 inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300"
          >
            <ArrowLeft className="h-3 w-3" />
            Biểu đồ 1 tuần
          </Link>
          <h1 className="text-2xl font-bold text-white">Hiệu suất 1 tháng</h1>
          <p className="mt-1 text-sm text-slate-400">4 tuần · trục Y · đường / nến / tròn</p>
        </div>
        <ChartModeSwitcher mode={chartMode} onChange={setChartMode} />
      </div>

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-24 text-slate-400">
          <Loader2 className="h-6 w-6 animate-spin" />
          Đang tải biểu đồ…
        </div>
      ) : error || !data ? (
        <p className="py-12 text-center text-rose-300">{error ?? 'Không có dữ liệu'}</p>
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-3">
            <PerformanceChart
              title="Auto · 28 ngày"
              subtitle="4 tuần lưu record"
              data={data.auto}
              accent="emerald"
              mode={chartMode}
              height={260}
            />
            <PerformanceChart
              title="Manual · 28 ngày"
              subtitle="4 tuần lưu record"
              data={data.manual}
              accent="violet"
              mode={chartMode}
              height={260}
            />
            <PerformanceChart
              title="Tổng · 28 ngày"
              subtitle="Auto + Manual"
              data={data.total}
              accent="amber"
              mode={chartMode}
              height={260}
            />
          </div>
          <p className="mt-4 text-center text-[10px] text-slate-600">
            Retention {data.retention_days} ngày · {data.point_count} snapshot
          </p>
        </>
      )}
    </main>
  );
}
