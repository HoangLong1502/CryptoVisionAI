"""Binance WebSocket bookTicker — sub-second live prices."""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings
from app.services.crypto_data import (
    COIN_REGISTRY,
    DEFAULT_WATCHLIST,
    GLOBAL_INDICES,
    _cache,
    _lock,
    crypto_market_session,
    sync_market_snapshot,
)

# Binance USDT spot pairs (MATIC → POL on Binance)
SYMBOL_TO_BINANCE: Dict[str, str] = {
    'BTC': 'btcusdt',
    'ETH': 'ethusdt',
    'BNB': 'bnbusdt',
    'SOL': 'solusdt',
    'XRP': 'xrpusdt',
    'ADA': 'adausdt',
    'DOGE': 'dogeusdt',
    'AVAX': 'avaxusdt',
    'DOT': 'dotusdt',
    'LINK': 'linkusdt',
    'MATIC': 'polusdt',
    'UNI': 'uniusdt',
    'ATOM': 'atomusdt',
    'LTC': 'ltcusdt',
    'TRX': 'trxusdt',
    'SHIB': 'shibusdt',
    'NEAR': 'nearusdt',
    'SUI': 'suiusdt',
}

BINANCE_TO_SYMBOL = {v.upper(): k for k, v in SYMBOL_TO_BINANCE.items()}

_live_prices: Dict[str, float] = {}
_broadcast_debounce_task: Optional[asyncio.Task] = None
_metadata_task: Optional[asyncio.Task] = None


def get_live_price(symbol: str) -> Optional[float]:
    return _live_prices.get(symbol.strip().upper())


def build_overview_from_cache() -> Dict[str, Any]:
    """Fast snapshot for WS push — merges Binance live prices into cached rows."""
    base = _cache.get('overview')
    markets = dict(_cache.get('markets') or {})
    if not markets and base:
        markets = {w['symbol']: w for w in base.get('watchlist', [])}

    watchlist = []
    for sym in DEFAULT_WATCHLIST:
        row = dict(markets.get(sym) or {'symbol': sym, 'price': 0, 'change': 0, 'change_pct': 0})
        meta = COIN_REGISTRY.get(sym, {})
        row.setdefault('name', meta.get('name', sym))
        row.setdefault('symbol', sym)
        live = _live_prices.get(sym)
        if live and live > 0:
            row['price'] = live
        watchlist.append(row)

    movers = sorted(watchlist, key=lambda x: float(x.get('change_pct') or 0), reverse=True)
    indices = []
    for sym in GLOBAL_INDICES:
        item = next((w for w in watchlist if w['symbol'] == sym), None)
        if item:
            indices.append({
                'symbol': sym,
                'price': float(item.get('price') or 0),
                'change': float(item.get('change_pct') or 0),
            })
        else:
            indices.append({'symbol': sym, 'price': 0.0, 'change': 0.0})

    return {
        'indices': indices,
        'watchlist': watchlist,
        'top_gainers': movers[:5],
        'top_losers': sorted(watchlist, key=lambda x: float(x.get('change_pct') or 0))[:5],
        'market_session': crypto_market_session(),
        'quote_source': 'Binance bookTicker (~200ms) · 24h stats from CoinGecko',
        'live_interval_ms': settings.live_broadcast_ms,
    }


def _apply_book_ticker(data: Dict[str, Any]) -> bool:
    sym = BINANCE_TO_SYMBOL.get(str(data.get('s', '')).upper())
    if not sym:
        return False
    bid = float(data.get('b') or 0)
    ask = float(data.get('a') or 0)
    if bid <= 0 and ask <= 0:
        return False
    if bid > 0 and ask > 0:
        price = (bid + ask) / 2
    else:
        price = bid or ask
    prev = _live_prices.get(sym)
    if prev is not None and abs(prev - price) < 1e-12:
        return False
    _live_prices[sym] = price
    markets = _cache.get('markets') or {}
    if sym in markets:
        markets[sym]['price'] = price
    return True


async def _schedule_broadcast() -> None:
    global _broadcast_debounce_task
    from app.services.market_ws import notify_market_update

    if _broadcast_debounce_task and not _broadcast_debounce_task.done():
        _broadcast_debounce_task.cancel()

    async def _debounced() -> None:
        try:
            await asyncio.sleep(settings.live_broadcast_ms / 1000.0)
            await notify_market_update()
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    _broadcast_debounce_task = asyncio.create_task(_debounced())


async def _fetch_binance_24h() -> None:
    """Refresh 24h change % from Binance (single REST call)."""
    symbols = [f'"{SYMBOL_TO_BINANCE[s].upper()}"' for s in DEFAULT_WATCHLIST if s in SYMBOL_TO_BINANCE]
    if not symbols:
        return
    url = f'{settings.binance_api_base}/api/v3/ticker/24hr'
    params = {'symbols': f'[{",".join(symbols)}]'}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(url, params=params)
            res.raise_for_status()
            rows = res.json()
    except Exception:
        return

    markets = _cache.setdefault('markets', {})
    for row in rows:
        pair = str(row.get('symbol', '')).upper()
        sym = BINANCE_TO_SYMBOL.get(pair)
        if not sym:
            continue
        change = float(row.get('priceChangePercent') or 0)
        price = float(row.get('lastPrice') or 0)
        if price > 0:
            _live_prices[sym] = price
        entry = dict(markets.get(sym) or {})
        meta = COIN_REGISTRY.get(sym, {})
        entry.update({
            'symbol': sym,
            'name': entry.get('name') or meta.get('name', sym),
            'coin_id': entry.get('coin_id') or meta.get('id'),
            'price': _live_prices.get(sym, price),
            'change': change,
            'change_pct': change,
            'volume_24h': float(row.get('quoteVolume') or 0),
            'high_24h': float(row.get('highPrice') or 0),
            'low_24h': float(row.get('lowPrice') or 0),
            'signal': 'bull' if change > 0.5 else 'bear' if change < -0.5 else 'flat',
            'signal_label': 'Bullish' if change > 0.5 else 'Bearish' if change < -0.5 else 'Neutral',
            'price_unit': 'USD',
        })
        markets[sym] = entry

    overview = build_overview_from_cache()
    async with _lock:
        _cache['overview'] = overview


async def _metadata_loop() -> None:
    while True:
        try:
            await _fetch_binance_24h()
        except Exception:
            pass
        await asyncio.sleep(settings.metadata_refresh_seconds)


async def _binance_ws_loop() -> None:
    import websockets

    streams = '/'.join(f'{SYMBOL_TO_BINANCE[s]}@bookTicker' for s in DEFAULT_WATCHLIST if s in SYMBOL_TO_BINANCE)
    url = f'{settings.binance_ws_base}/stream?streams={streams}'

    while True:
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                async for raw in ws:
                    msg = json.loads(raw)
                    data = msg.get('data') if isinstance(msg.get('data'), dict) else msg
                    if isinstance(data, dict) and _apply_book_ticker(data):
                        await _schedule_broadcast()
        except Exception:
            await asyncio.sleep(2)


async def start_binance_realtime() -> None:
    global _metadata_task
    try:
        await sync_market_snapshot()
    except Exception:
        try:
            await _fetch_binance_24h()
            async with _lock:
                _cache['overview'] = build_overview_from_cache()
        except Exception:
            pass

    asyncio.create_task(_binance_ws_loop())
    if _metadata_task is None or _metadata_task.done():
        _metadata_task = asyncio.create_task(_metadata_loop())
