'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { ArrowLeft, Loader2 } from 'lucide-react';
import PnlLineChart from '../../components/performance/PnlLineChart';
import { getPerformanceMonth, type PerformanceChartData } from '../../lib/api';

export default function PerformanceMonthPage() {
  const [data, setData] = useState<PerformanceChartData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
      <div className="mb-6">
        <Link
          href="/performance"
          className="mb-2 inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300"
        >
          <ArrowLeft className="h-3 w-3" />
          Biểu đồ 1 tuần
        </Link>
        <h1 className="text-2xl font-bold text-white">Hiệu suất 1 tháng</h1>
        <p className="mt-1 text-sm text-slate-400">
          4 tuần dữ liệu lưu trữ · Auto · Manual · Tổng
        </p>
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
            <PnlLineChart
              title="Auto Trading · 28 ngày"
              subtitle="4 tuần lưu record"
              data={data.auto}
              accent="emerald"
              height={260}
            />
            <PnlLineChart
              title="Manual Trading · 28 ngày"
              subtitle="4 tuần lưu record"
              data={data.manual}
              accent="violet"
              height={260}
            />
            <PnlLineChart
              title="Tổng · 28 ngày"
              subtitle="Auto + Manual"
              data={data.total}
              accent="amber"
              height={260}
            />
          </div>
          <p className="mt-4 text-center text-[10px] text-slate-600">
            Retention {data.retention_days} ngày · {data.point_count} snapshot · cập nhật mỗi giờ + sau mỗi lệnh
          </p>
        </>
      )}
    </main>
  );
}
