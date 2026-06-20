'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { ArrowLeft, Calendar, Loader2 } from 'lucide-react';
import PnlLineChart from '../../components/performance/PnlLineChart';
import { getPerformanceWeek, type PerformanceChartData } from '../../lib/api';

function ChartGrid({ data, periodLabel }: { readonly data: PerformanceChartData; readonly periodLabel: string }) {
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <PnlLineChart
        title="Auto Trading"
        subtitle={`Lãi/lỗ ${periodLabel} · lệnh AI bot`}
        data={data.auto}
        accent="emerald"
      />
      <PnlLineChart
        title="Manual Trading"
        subtitle={`Lãi/lỗ ${periodLabel} · mua/bán tay`}
        data={data.manual}
        accent="violet"
      />
      <PnlLineChart
        title="Tổng (Auto + Manual)"
        subtitle={`Lãi/lỗ ${periodLabel} · toàn ví ảo`}
        data={data.total}
        accent="amber"
      />
    </div>
  );
}

export default function PerformanceWeekPage() {
  const [data, setData] = useState<PerformanceChartData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPerformanceWeek()
      .then(setData)
      .catch(() => setError('Không tải được dữ liệu biểu đồ'))
      .finally(() => setLoading(false));
    const t = setInterval(() => {
      getPerformanceWeek().then(setData).catch(() => {});
    }, 60_000);
    return () => clearInterval(t);
  }, []);

  return (
    <main className="mx-auto max-w-6xl px-4 py-6">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link href="/" className="mb-2 inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300">
            <ArrowLeft className="h-3 w-3" />
            Dashboard
          </Link>
          <h1 className="text-2xl font-bold text-white">Hiệu suất Paper Trading</h1>
          <p className="mt-1 text-sm text-slate-400">
            Biểu đồ tăng/giảm 7 ngày · snapshot mỗi giờ · lưu tối đa 4 tuần
          </p>
        </div>
        <Link
          href="/performance/month"
          className="inline-flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm font-semibold text-amber-200 hover:bg-amber-500/20"
        >
          <Calendar className="h-4 w-4" />
          Xem 1 tháng (4 tuần)
        </Link>
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
          <ChartGrid data={data} periodLabel="7 ngày" />
          <p className="mt-4 text-center text-[10px] text-slate-600">
            {data.point_count} điểm dữ liệu · Auto/Manual tính trên nửa vốn ảo ($5,000/kênh) · Tổng trên $10,000
          </p>
        </>
      )}
    </main>
  );
}
