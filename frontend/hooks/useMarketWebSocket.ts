'use client';

import { useEffect, useRef, useState } from 'react';
import { marketWsUrl } from '../lib/api';
import type { DashboardData } from '../components/dashboard/DashboardHome';

export type MarketWsMessage = {
  type: string;
  watchlist?: DashboardData['watchlist'];
  indices?: DashboardData['indices'];
  top_gainers?: DashboardData['top_gainers'];
  top_losers?: DashboardData['top_losers'];
  quote_source?: string;
};

function numPrice(v: unknown): number {
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? n : 0;
}

function patchWatchlist(prev: DashboardData['watchlist'], incoming: DashboardData['watchlist'] | undefined) {
  if (!incoming?.length) return prev;
  const bySym = new Map(incoming.map((row) => [String(row.symbol).toUpperCase(), row]));
  let changed = false;
  const next = (prev ?? []).map((item) => {
    const sym = typeof item === 'string' ? item : item.symbol;
    const upd = bySym.get(String(sym).toUpperCase());
    if (!upd) return typeof item === 'string' ? { symbol: item, price: 0, change: 0 } : item;
    const base = typeof item === 'string' ? { symbol: item, price: 0, change: 0 } : item;
    const newPrice = numPrice(upd.price ?? base.price);
    const oldPrice = numPrice(base.price);
    if (Math.abs(newPrice - oldPrice) > 1e-12) changed = true;
    return { ...base, ...upd, price: newPrice, change_pct: upd.change_pct ?? upd.change ?? base.change_pct };
  });
  return changed ? next : prev;
}

function patchIndices(prev: DashboardData['indices'], incoming: DashboardData['indices'] | undefined) {
  if (!incoming?.length) return prev;
  let changed = false;
  const next = incoming.map((row) => {
    const old = prev?.find((p) => p.symbol === row.symbol);
    const price = numPrice(row.price);
    const oldPrice = numPrice(old?.price);
    if (Math.abs(price - oldPrice) > 1e-12) changed = true;
    return { ...row, price, change: numPrice(row.change) };
  });
  return changed ? next : prev;
}

export function useMarketWebSocket(
  data: DashboardData | null,
  setData: React.Dispatch<React.SetStateAction<DashboardData | null>>,
) {
  const [connected, setConnected] = useState(false);
  const dataRef = useRef(data);
  dataRef.current = data;

  useEffect(() => {
    let ws: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let closed = false;

    const connect = () => {
      if (closed) return;
      try {
        ws = new WebSocket(marketWsUrl());
      } catch {
        retryTimer = setTimeout(connect, 5000);
        return;
      }

      ws.onopen = () => {
        setConnected(true);
        ws?.send('ping');
      };

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data as string) as MarketWsMessage;
          if (msg.type !== 'market_update') return;

          setData((prev) => {
            if (!prev) {
              return {
                indices: msg.indices ?? [],
                watchlist: msg.watchlist ?? [],
                top_gainers: msg.top_gainers ?? [],
                top_losers: msg.top_losers ?? [],
                quote_source: msg.quote_source ?? '',
              };
            }
            const watchlist = patchWatchlist(prev.watchlist, msg.watchlist);
            const indices = patchIndices(prev.indices, msg.indices);
            if (watchlist === prev.watchlist && indices === prev.indices) return prev;
            return {
              ...prev,
              watchlist,
              indices,
              quote_source: msg.quote_source ?? prev.quote_source,
            };
          });
        } catch {
          /* ignore */
        }
      };

      ws.onclose = () => {
        setConnected(false);
        if (!closed) retryTimer = setTimeout(connect, 4000);
      };

      ws.onerror = () => ws?.close();
    };

    connect();
    return () => {
      closed = true;
      if (retryTimer) clearTimeout(retryTimer);
      ws?.close();
      setConnected(false);
    };
  }, [setData]);

  return { wsConnected: connected };
}
