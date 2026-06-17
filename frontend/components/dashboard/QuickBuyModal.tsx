'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { X } from 'lucide-react';
import { getPaperWallet } from '../../lib/api';
import { PaperBuyPanel } from './PaperWallet';

export default function QuickBuyModal({
  symbol,
  livePrice,
  onClose,
  onSuccess,
}: {
  readonly symbol: string;
  readonly livePrice?: number;
  readonly onClose: () => void;
  readonly onSuccess?: () => void;
}) {
  const queryClient = useQueryClient();
  const { data: wallet } = useQuery({
    queryKey: ['paperWallet'],
    queryFn: getPaperWallet,
    staleTime: 2_000,
  });

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
        className="w-full max-w-md rounded-2xl border border-white/10 bg-slate-950 p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between gap-2">
          <h2 className="font-mono text-lg font-bold text-white">Mua {symbol}</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-white/10 bg-white/5 p-2 text-slate-300 hover:bg-white/10"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <PaperBuyPanel
          symbol={symbol}
          livePrice={livePrice}
          cashUsd={wallet?.cash_usd}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ['paperWallet'] });
            onSuccess?.();
          }}
        />
      </div>
    </div>
  );
}
