"""Custom watchlist — persist user-added coins and register them for full market support."""
from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.services.crypto_data import COIN_REGISTRY, DEFAULT_WATCHLIST

_lock = threading.Lock()
_store_path = Path(settings.custom_watchlist_path)

# symbol -> binance pair (lowercase), includes built-in + custom
_extra_binance_pairs: Dict[str, str] = {}


def _load_raw() -> Dict[str, Any]:
    if _store_path.is_file():
        try:
            data = json.loads(_store_path.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError, TypeError):
            pass
    return {'coins': []}


def _save_raw(data: Dict[str, Any]) -> None:
    _store_path.parent.mkdir(parents=True, exist_ok=True)
    _store_path.write_text(json.dumps(data, indent=2), encoding='utf-8')


def get_custom_symbols() -> List[str]:
    with _lock:
        return [str(c.get('symbol', '')).upper() for c in _load_raw().get('coins', []) if c.get('symbol')]


def get_effective_watchlist() -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for sym in list(DEFAULT_WATCHLIST) + get_custom_symbols():
        su = sym.upper()
        if su not in seen:
            seen.add(su)
            out.append(su)
    return out


def is_custom_symbol(symbol: str) -> bool:
    return symbol.strip().upper() in get_custom_symbols()


def get_binance_pair(symbol: str) -> Optional[str]:
    from app.services.binance_realtime import SYMBOL_TO_BINANCE

    sym = symbol.strip().upper()
    return SYMBOL_TO_BINANCE.get(sym) or _extra_binance_pairs.get(sym)


def get_all_binance_pairs() -> Dict[str, str]:
    from app.services.binance_realtime import SYMBOL_TO_BINANCE

    merged = dict(SYMBOL_TO_BINANCE)
    merged.update(_extra_binance_pairs)
    return merged


def _register_coin(symbol: str, coin_id: str, name: str, binance_pair: Optional[str] = None) -> None:
    sym = symbol.strip().upper()
    COIN_REGISTRY[sym] = {'id': coin_id, 'name': name}
    if binance_pair:
        _extra_binance_pairs[sym] = binance_pair.lower()
        from app.services.binance_realtime import register_binance_pair

        register_binance_pair(sym, binance_pair.lower())


def bootstrap_custom_watchlist() -> None:
    """Load saved custom coins into runtime registry on startup."""
    with _lock:
        for entry in _load_raw().get('coins', []):
            sym = str(entry.get('symbol', '')).upper()
            if not sym or sym in DEFAULT_WATCHLIST:
                continue
            coin_id = str(entry.get('id') or entry.get('coin_id') or sym.lower())
            name = str(entry.get('name') or sym)
            pair = entry.get('binance_pair')
            COIN_REGISTRY[sym] = {'id': coin_id, 'name': name}
            if pair:
                _extra_binance_pairs[sym] = str(pair).lower()
                from app.services.binance_realtime import register_binance_pair

                register_binance_pair(sym, str(pair).lower())


async def search_coins(query: str, limit: int = 8) -> List[Dict[str, Any]]:
    q = query.strip()
    if len(q) < 1:
        return []
    url = f'{settings.coingecko_base}/search'
    params = {'query': q}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(url, params=params)
            if res.status_code == 429:
                return _fallback_search(q, limit)
            res.raise_for_status()
            data = res.json()
    except httpx.HTTPError:
        return _fallback_search(q, limit)

    coins = data.get('coins') or []
    out: List[Dict[str, Any]] = []
    for row in coins[:limit]:
        sym = str(row.get('symbol', '')).upper()
        if not sym:
            continue
        out.append({
            'symbol': sym,
            'name': row.get('name') or sym,
            'coin_id': row.get('id'),
            'market_cap_rank': row.get('market_cap_rank'),
            'already_listed': sym in get_effective_watchlist(),
        })
    return out


def _fallback_search(query: str, limit: int) -> List[Dict[str, Any]]:
    q = query.strip().upper()
    out: List[Dict[str, Any]] = []
    for sym, meta in COIN_REGISTRY.items():
        if q in sym or q in meta.get('name', '').upper():
            out.append({
                'symbol': sym,
                'name': meta.get('name', sym),
                'coin_id': meta.get('id'),
                'market_cap_rank': None,
                'already_listed': sym in get_effective_watchlist(),
            })
        if len(out) >= limit:
            break
    return out


async def _resolve_binance_pair(symbol: str) -> Optional[str]:
    from app.services.binance_realtime import SYMBOL_TO_BINANCE

    sym = symbol.strip().upper()
    existing = SYMBOL_TO_BINANCE.get(sym) or _extra_binance_pairs.get(sym)
    if existing:
        return existing

    candidates = [f'{sym}USDT']
    if sym == 'MATIC':
        candidates.insert(0, 'POLUSDT')

    async with httpx.AsyncClient(timeout=10.0) as client:
        for pair in candidates:
            try:
                res = await client.get(
                    f'{settings.binance_api_base}/api/v3/ticker/price',
                    params={'symbol': pair},
                )
                if res.status_code == 200:
                    return pair.lower()
            except httpx.HTTPError:
                continue
    return None


async def _fetch_coin_meta(coin_id: str) -> Optional[Dict[str, str]]:
    url = f'{settings.coingecko_base}/coins/{coin_id}'
    params = {
        'localization': 'false',
        'tickers': 'false',
        'market_data': 'false',
        'community_data': 'false',
        'developer_data': 'false',
        'sparkline': 'false',
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(url, params=params)
            if res.status_code == 404:
                return None
            res.raise_for_status()
            data = res.json()
    except httpx.HTTPError:
        return None
    sym = str(data.get('symbol', '')).upper()
    if not sym:
        return None
    return {'symbol': sym, 'id': coin_id, 'name': str(data.get('name') or sym)}


async def add_coin(*, symbol: Optional[str] = None, coin_id: Optional[str] = None) -> Dict[str, Any]:
    meta: Optional[Dict[str, str]] = None

    if coin_id:
        meta = await _fetch_coin_meta(coin_id.strip().lower())
        if not meta:
            raise ValueError(f'Coin id "{coin_id}" not found on CoinGecko')
    elif symbol:
        sym = symbol.strip().upper()
        if sym in COIN_REGISTRY:
            meta = {'symbol': sym, 'id': COIN_REGISTRY[sym]['id'], 'name': COIN_REGISTRY[sym]['name']}
        else:
            results = await search_coins(sym, limit=5)
            exact = next((r for r in results if r['symbol'] == sym), None)
            if exact and exact.get('coin_id'):
                meta = {'symbol': sym, 'id': exact['coin_id'], 'name': exact['name']}
            elif len(results) == 1 and results[0].get('coin_id'):
                meta = {
                    'symbol': results[0]['symbol'],
                    'id': results[0]['coin_id'],
                    'name': results[0]['name'],
                }
            else:
                raise ValueError(f'Could not resolve "{sym}". Search and pick a coin id.')
    else:
        raise ValueError('symbol or coin_id required')

    sym = meta['symbol']
    if sym in get_effective_watchlist() and sym not in get_custom_symbols():
        raise ValueError(f'{sym} is already in the default watchlist')

    binance_pair = await _resolve_binance_pair(sym)

    with _lock:
        raw = _load_raw()
        coins: List[Dict[str, Any]] = raw.setdefault('coins', [])
        coins = [c for c in coins if str(c.get('symbol', '')).upper() != sym]
        entry = {
            'symbol': sym,
            'id': meta['id'],
            'name': meta['name'],
            'binance_pair': binance_pair,
        }
        coins.append(entry)
        raw['coins'] = coins
        _save_raw(raw)

    _register_coin(sym, meta['id'], meta['name'], binance_pair)

    from app.services.binance_realtime import request_stream_refresh
    from app.services.crypto_data import bump_market_cache, sync_market_snapshot
    from app.services.market_ws import notify_market_update

    bump_market_cache()
    await sync_market_snapshot()
    request_stream_refresh()
    await notify_market_update()

    from app.services.coin_screener import request_signal_refresh

    asyncio.create_task(request_signal_refresh(sym))

    return {
        'ok': True,
        'symbol': sym,
        'name': meta['name'],
        'coin_id': meta['id'],
        'binance_pair': binance_pair,
        'has_live_price': binance_pair is not None,
        'is_custom': sym not in DEFAULT_WATCHLIST,
        'message': f'Added {sym} ({meta["name"]})' + ('' if binance_pair else ' — live Binance pair not found, using CoinGecko'),
    }


async def remove_coin(symbol: str) -> Dict[str, Any]:
    sym = symbol.strip().upper()
    if sym in DEFAULT_WATCHLIST:
        raise ValueError(f'Cannot remove default coin {sym}')
    if sym not in get_custom_symbols():
        raise ValueError(f'{sym} is not in your custom watchlist')

    with _lock:
        raw = _load_raw()
        raw['coins'] = [c for c in raw.get('coins', []) if str(c.get('symbol', '')).upper() != sym]
        _save_raw(raw)

    _extra_binance_pairs.pop(sym, None)
    if sym not in DEFAULT_WATCHLIST:
        COIN_REGISTRY.pop(sym, None)

    from app.services.binance_realtime import request_stream_refresh, unregister_binance_pair
    from app.services.crypto_data import bump_market_cache, sync_market_snapshot
    from app.services.market_ws import notify_market_update

    unregister_binance_pair(sym)
    bump_market_cache()
    await sync_market_snapshot()
    request_stream_refresh()
    await notify_market_update()

    return {'ok': True, 'symbol': sym, 'message': f'Removed {sym} from watchlist'}


def list_custom_coins() -> List[Dict[str, Any]]:
    with _lock:
        return list(_load_raw().get('coins', []))
