'use client';

import type { ReactNode } from 'react';
import { usePriceFlash, type FlashDirection } from '../../hooks/usePriceFlash';

const FLASH_CLASS: Record<FlashDirection, string> = {
  up: 'animate-price-flash-up',
  down: 'animate-price-flash-down',
};

export default function FlashPrice({
  symbol,
  price,
  className = '',
  children,
}: {
  readonly symbol: string;
  readonly price: number | string;
  readonly className?: string;
  readonly children: ReactNode;
}) {
  const { direction, pulse } = usePriceFlash(symbol, price);
  const flashCls = direction ? FLASH_CLASS[direction] : '';

  return (
    <span className={`inline-flex justify-end ${className}`.trim()}>
      <span
        key={pulse || 'idle'}
        className={`inline-block rounded-lg px-2 py-1 tabular-nums ${flashCls}`.trim()}
      >
        {children}
      </span>
    </span>
  );
}
