'use client';

import { useLayoutEffect, useRef, useState } from 'react';

export type FlashDirection = 'up' | 'down';

export type PriceFlashState = {
  direction: FlashDirection | null;
  /** Increments on each tick so CSS animation restarts */
  pulse: number;
};

function normalizePrice(price: number | string): number {
  const n = typeof price === 'number' ? price : Number(price);
  return Number.isFinite(n) ? n : 0;
}

export function usePriceFlash(symbol: string, price: number | string): PriceFlashState {
  const prevRef = useRef<number | null>(null);
  const [state, setState] = useState<PriceFlashState>({ direction: null, pulse: 0 });

  useLayoutEffect(() => {
    const n = normalizePrice(price);
    if (n <= 0) return;

    const prev = prevRef.current;
    if (prev !== null && Math.abs(prev - n) > 1e-12) {
      setState({
        direction: n > prev ? 'up' : 'down',
        pulse: Date.now(),
      });
    }
    prevRef.current = n;
  }, [symbol, price]);

  return state;
}
