"""CoinGecko data + in-memory cache for realtime crypto prices."""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.config import settings

# symbol -> coingecko id
COIN_REGISTRY: Dict[str, Dict[str, str]] = {
    'BTC': {'id': 'bitcoin', 'name': 'Bitcoin'},
    'ETH': {'id': 'ethereum', 'name': 'Ethereum'},
    'BNB': {'id': 'binancecoin', 'name': 'BNB'},
    'SOL': {'id': 'solana', 'name': 'Solana'},
    'XRP': {'id': 'ripple', 'name': 'XRP'},
    'ADA': {'id': 'cardano', 'name': 'Cardano'},
    'DOGE': {'id': 'dogecoin', 'name': 'Dogecoin'},
    'AVAX': {'id': 'avalanche-2', 'name': 'Avalanche'},
    'DOT': {'id': 'polkadot', 'name': 'Polkadot'},
    'LINK': {'id': 'chainlink', 'name': 'Chainlink'},
    'MATIC': {'id': 'matic-network', 'name': 'Polygon'},
    'UNI': {'id': 'uniswap', 'name': 'Uniswap'},
    'ATOM': {'id': 'cosmos', 'name': 'Cosmos'},
    'LTC': {'id': 'litecoin', 'name': 'Litecoin'},
    'TRX': {'id': 'tron', 'name': 'TRON'},
    'SHIB': {'id': 'shiba-inu', 'name': 'Shiba Inu'},
    'NEAR': {'id': 'near', 'name': 'NEAR Protocol'},
    'SUI': {'id': 'sui', 'name': 'Sui'},
}

DEFAULT_WATCHLIST = list(COIN_REGISTRY.keys())
GLOBAL_INDICES = ['BTC', 'ETH', 'BNB']


def _active_watchlist() -> List[str]:
    from app.services.watchlist_store import get_effective_watchlist

    return get_effective_watchlist()

DEMO_PRICES: Dict[str, Dict[str, float]] = {
    'BTC': {'price': 97000, 'change_pct': 1.2, 'volume_24h': 25e9, 'market_cap': 1.9e12},
    'ETH': {'price': 3800, 'change_pct': 0.8, 'volume_24h': 12e9, 'market_cap': 460e9},
    'BNB': {'price': 680, 'change_pct': -0.3, 'volume_24h': 1.5e9, 'market_cap': 100e9},
    'SOL': {'price': 240, 'change_pct': 2.1, 'volume_24h': 3e9, 'market_cap': 110e9},
    'XRP': {'price': 2.5, 'change_pct': -1.0, 'volume_24h': 4e9, 'market_cap': 140e9},
}


def _demo_watchlist_rows() -> List[Dict[str, Any]]:
    rows = []
    for sym in _active_watchlist():
        demo = DEMO_PRICES.get(sym, {'price': 1.0, 'change_pct': 0, 'volume_24h': 1e6, 'market_cap': 1e8})
        meta = COIN_REGISTRY.get(sym, {})
        rows.append(_market_row_to_watchlist({
            'symbol': sym.lower(),
            'id': meta.get('id', sym.lower()),
            'name': meta.get('name', sym),
            'current_price': demo['price'],
            'price_change_percentage_24h': demo['change_pct'],
            'total_volume': demo['volume_24h'],
            'market_cap': demo['market_cap'],
            'high_24h': demo['price'] * 1.02,
            'low_24h': demo['price'] * 0.98,
        }))
    return rows

_cache: Dict[str, Any] = {'ts': 0.0, 'markets': {}, 'overview': None, 'details': {}, 'history': {}}
_lock = asyncio.Lock()
DETAIL_CACHE_SECONDS = 60
HISTORY_CACHE_SECONDS = 300


def bump_market_cache() -> None:
    """Force next sync_market_snapshot to refetch."""
    _cache['ts'] = 0.0


def symbol_to_id(symbol: str) -> Optional[str]:
    meta = COIN_REGISTRY.get(symbol.strip().upper())
    return meta['id'] if meta else None


def id_to_symbol(coin_id: str) -> Optional[str]:
    for sym, meta in COIN_REGISTRY.items():
        if meta['id'] == coin_id:
            return sym
    return None


async def _fetch_markets() -> List[Dict[str, Any]]:
    symbols = _active_watchlist()
    ids = ','.join(COIN_REGISTRY[s]['id'] for s in symbols if s in COIN_REGISTRY)
    url = f'{settings.coingecko_base}/coins/markets'
    params = {
        'vs_currency': 'usd',
        'ids': ids,
        'order': 'market_cap_desc',
        'sparkline': 'false',
        'price_change_percentage': '24h',
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.get(url, params=params)
        if res.status_code == 429:
            raise httpx.HTTPStatusError('Rate limited', request=res.request, response=res)
        res.raise_for_status()
        return res.json()


def _market_row_to_watchlist(row: Dict[str, Any]) -> Dict[str, Any]:
    sym = str(row.get('symbol', '')).upper()
    meta = COIN_REGISTRY.get(sym, {})
    price = float(row.get('current_price') or 0)
    change = float(row.get('price_change_percentage_24h') or 0)
    sig = 'bull' if change > 0.5 else 'bear' if change < -0.5 else 'flat'
    sig_label = 'Bullish' if sig == 'bull' else 'Bearish' if sig == 'bear' else 'Neutral'
    return {
        'symbol': sym,
        'name': row.get('name') or meta.get('name', sym),
        'coin_id': row.get('id') or meta.get('id'),
        'price': price,
        'change': change,
        'change_pct': change,
        'volume_24h': float(row.get('total_volume') or 0),
        'market_cap': float(row.get('market_cap') or 0),
        'high_24h': float(row.get('high_24h') or 0),
        'low_24h': float(row.get('low_24h') or 0),
        'signal': sig,
        'signal_label': sig_label,
        'price_unit': 'USD',
        'quote_source_note': 'CoinGecko realtime (~10s)',
    }


async def sync_market_snapshot() -> Dict[str, Any]:
    async with _lock:
        now = time.monotonic()
        if _cache.get('overview') and now - float(_cache.get('ts') or 0) < settings.sync_ttl_seconds:
            return _cache['overview']

        try:
            rows = await _fetch_markets()
        except httpx.HTTPError:
            if _cache.get('overview'):
                return _cache['overview']
            rows = []
        if not rows:
            watchlist = _demo_watchlist_rows()
            overview = {
                'indices': [{'symbol': s, 'price': DEMO_PRICES.get(s, {}).get('price', 0), 'change': DEMO_PRICES.get(s, {}).get('change_pct', 0)} for s in GLOBAL_INDICES],
                'watchlist': watchlist,
                'top_gainers': sorted(watchlist, key=lambda x: x['change_pct'], reverse=True)[:5],
                'top_losers': sorted(watchlist, key=lambda x: x['change_pct'])[:5],
                'market_session': crypto_market_session(),
                'quote_source': 'Demo data (CoinGecko rate limit) — reference prices only',
                'as_of': datetime.now(timezone.utc).isoformat(),
            }
            _cache['overview'] = overview
            _cache['markets'] = {w['symbol']: w for w in watchlist}
            _cache['ts'] = now
            return overview
        by_symbol = {str(r.get('symbol', '')).upper(): r for r in rows}
        watchlist = []
        for sym in _active_watchlist():
            row = by_symbol.get(sym)
            if row:
                item = _market_row_to_watchlist(row)
            elif sym in COIN_REGISTRY:
                item = _market_row_to_watchlist({
                    'symbol': sym.lower(),
                    'id': COIN_REGISTRY[sym]['id'],
                    'name': COIN_REGISTRY[sym]['name'],
                    'current_price': 0,
                    'price_change_percentage_24h': 0,
                    'total_volume': 0,
                    'market_cap': 0,
                    'high_24h': 0,
                    'low_24h': 0,
                })
            else:
                continue
            from app.services.watchlist_store import is_custom_symbol

            item['is_custom'] = is_custom_symbol(sym)
            watchlist.append(item)

        movers = sorted(watchlist, key=lambda x: x['change_pct'], reverse=True)
        top_gainers = movers[:5]
        top_losers = sorted(watchlist, key=lambda x: x['change_pct'])[:5]

        indices = []
        for sym in GLOBAL_INDICES:
            item = next((w for w in watchlist if w['symbol'] == sym), None)
            if item:
                indices.append({'symbol': sym, 'price': item['price'], 'change': item['change_pct']})
            else:
                indices.append({'symbol': sym, 'price': 0.0, 'change': 0.0})

        overview = {
            'indices': indices,
            'watchlist': watchlist,
            'top_gainers': top_gainers,
            'top_losers': top_losers,
            'market_session': crypto_market_session(),
            'quote_source': 'Prices from CoinGecko — crypto markets trade 24/7',
            'as_of': datetime.now(timezone.utc).isoformat(),
        }
        _cache['overview'] = overview
        _cache['markets'] = {w['symbol']: w for w in watchlist}
        _cache['ts'] = now
        return overview


def _detail_from_market_row(sym: str, row: Dict[str, Any]) -> Dict[str, Any]:
    meta = COIN_REGISTRY.get(sym, {})
    price = float(row.get('price') or 0)
    vol = float(row.get('volume_24h') or 0)
    mcap = float(row.get('market_cap') or 0)
    vol_mcap = (vol / mcap * 100) if mcap > 0 else 0
    return {
        'symbol': sym,
        'name': row.get('name') or meta.get('name', sym),
        'coin_id': row.get('coin_id') or meta.get('id'),
        'rank': 0,
        'prices': {
            'last': price,
            'high_24h': float(row.get('high_24h') or 0),
            'low_24h': float(row.get('low_24h') or 0),
            'ath': 0,
            'atl': 0,
        },
        'change_pct': float(row.get('change_pct') or 0),
        'volume_24h': vol,
        'market_cap': mcap,
        'circulating_supply': 0,
        'volume_to_mcap_pct': round(vol_mcap, 2),
        'order_flow': {
            'pressure': 'normal',
            'pressure_label': row.get('quote_source_note', 'Aggregated market data'),
        },
        'quote_source': 'CoinGecko markets (fallback)',
        'market_session': crypto_market_session(),
    }


def build_detail_from_market_row(sym: str, row: Dict[str, Any]) -> Dict[str, Any]:
    return _detail_from_market_row(sym, row)


async def get_coin_detail(symbol: str) -> Optional[Dict[str, Any]]:
    sym = symbol.strip().upper()
    meta = COIN_REGISTRY.get(sym)
    if not meta:
        return None

    now = time.monotonic()
    cached = (_cache.get('details') or {}).get(sym)
    if cached and now - cached['ts'] < DETAIL_CACHE_SECONDS:
        return cached['body']

    market_row = (_cache.get('markets') or {}).get(sym)
    if market_row and market_row.get('price') and now - float(_cache.get('ts') or 0) < DETAIL_CACHE_SECONDS:
        body = build_detail_from_market_row(sym, market_row)
        _cache.setdefault('details', {})[sym] = {'ts': now, 'body': body}
        return body

    coin_id = meta['id']
    url = f'{settings.coingecko_base}/coins/{coin_id}'
    params = {
        'localization': 'false',
        'tickers': 'false',
        'community_data': 'false',
        'developer_data': 'false',
        'sparkline': 'false',
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(url, params=params)
            if res.status_code == 404:
                return None
            if res.status_code == 429:
                if cached:
                    return cached['body']
                if market_row:
                    return _detail_from_market_row(sym, market_row)
                await sync_market_snapshot()
                market_row = (_cache.get('markets') or {}).get(sym)
                if market_row:
                    return _detail_from_market_row(sym, market_row)
                return _detail_from_market_row(sym, {'symbol': sym, 'price': 0, 'change_pct': 0, 'volume_24h': 0, 'market_cap': 0})
            res.raise_for_status()
            data = res.json()
    except httpx.HTTPError:
        if cached:
            return cached['body']
        if market_row:
            return _detail_from_market_row(sym, market_row)
        raise

    md = data.get('market_data') or {}
    price = float(md.get('current_price', {}).get('usd') or 0)
    change = float(md.get('price_change_percentage_24h') or 0)
    vol = float(md.get('total_volume', {}).get('usd') or 0)
    mcap = float(md.get('market_cap', {}).get('usd') or 0)
    ath = float(md.get('ath', {}).get('usd') or 0)
    atl = float(md.get('atl', {}).get('usd') or 0)
    circ = float(md.get('circulating_supply') or 0)
    rank = int(data.get('market_cap_rank') or 0)

    vol_mcap = (vol / mcap * 100) if mcap > 0 else 0
    if vol_mcap > 15:
        pressure = 'high_activity'
        pressure_label = 'High trading volume — strong market interest'
    elif vol_mcap > 5:
        pressure = 'normal'
        pressure_label = 'Stable volume relative to market cap'
    else:
        pressure = 'low'
        pressure_label = 'Low volume — limited liquidity, watch for slippage'

    body = {
        'symbol': sym,
        'name': data.get('name') or meta['name'],
        'coin_id': coin_id,
        'rank': rank,
        'prices': {
            'last': price,
            'high_24h': float(md.get('high_24h', {}).get('usd') or 0),
            'low_24h': float(md.get('low_24h', {}).get('usd') or 0),
            'ath': ath,
            'atl': atl,
        },
        'change_pct': change,
        'volume_24h': vol,
        'market_cap': mcap,
        'circulating_supply': circ,
        'volume_to_mcap_pct': round(vol_mcap, 2),
        'order_flow': {
            'pressure': pressure,
            'pressure_label': pressure_label,
        },
        'community': {
            'twitter_followers': (data.get('community_data') or {}).get('twitter_followers'),
            'reddit_subscribers': (data.get('community_data') or {}).get('reddit_subscribers'),
        },
        'description': (data.get('description') or {}).get('en', '')[:400],
        'quote_source': 'CoinGecko — near real-time',
        'market_session': crypto_market_session(),
    }
    _cache.setdefault('details', {})[sym] = {'ts': now, 'body': body}
    return body


async def get_historical_prices(symbol: str, days: int = 60) -> List[Dict[str, Any]]:
    sym = symbol.strip().upper()
    coin_id = symbol_to_id(sym)
    if not coin_id:
        return []

    cache_key = f'{sym}:{days}'
    now = time.monotonic()
    cached = (_cache.get('history') or {}).get(cache_key)
    if cached and now - cached['ts'] < HISTORY_CACHE_SECONDS:
        return cached['body']

    market_row = (_cache.get('markets') or {}).get(sym)
    if market_row and market_row.get('price'):
        synthetic = _synthetic_history_from_market(sym, days)
        if synthetic:
            _cache.setdefault('history', {})[cache_key] = {'ts': now, 'body': synthetic}
            return synthetic

    url = f'{settings.coingecko_base}/coins/{coin_id}/market_chart'
    params = {'vs_currency': 'usd', 'days': str(days), 'interval': 'daily'}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(url, params=params)
            if res.status_code == 429 and cached:
                return cached['body']
            res.raise_for_status()
            data = res.json()
    except httpx.HTTPError:
        if cached:
            return cached['body']
        return _synthetic_history_from_market(sym, days)

    prices = data.get('prices') or []
    volumes = {int(v[0]): float(v[1]) for v in (data.get('total_volumes') or [])}
    out: List[Dict[str, Any]] = []
    for ts_ms, close in prices:
        ts = int(ts_ms)
        out.append({
            'date': datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime('%Y-%m-%d'),
            'close': float(close),
            'volume': volumes.get(ts, 0.0),
        })
    _cache.setdefault('history', {})[cache_key] = {'ts': now, 'body': out}
    return out


def _synthetic_history_from_market(sym: str, days: int) -> List[Dict[str, Any]]:
    """Fallback when rate limited — minimal price series from current quote."""
    row = (_cache.get('markets') or {}).get(sym)
    if not row:
        return []
    price = float(row.get('price') or 0)
    if price <= 0:
        return []
    change = float(row.get('change_pct') or 0) / 100
    out: List[Dict[str, Any]] = []
    for i in range(days, -1, -1):
        factor = 1 + (change * (days - i) / max(days, 1) * 0.3)
        out.append({
            'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
            'close': price / factor,
            'volume': float(row.get('volume_24h') or 0),
        })
    out[-1]['close'] = price
    return out


def crypto_market_session() -> Dict[str, Any]:
    return {
        'label': 'Crypto 24/7',
        'phase': 'always_open',
        'is_trading_hours': True,
        'is_trading_day': True,
    }


async def periodic_market_sync() -> None:
    from app.services.market_ws import notify_market_update

    while True:
        try:
            await sync_market_snapshot()
            await notify_market_update()
        except Exception:
            pass
        await asyncio.sleep(settings.sync_ttl_seconds)
