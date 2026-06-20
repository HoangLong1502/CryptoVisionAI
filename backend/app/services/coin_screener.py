"""Background AI screener — marks watchlist coins the committee rates as buy."""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

from app.core.config import settings

_signal_cache: Dict[str, Dict[str, Any]] = {}
_cache_ts: Dict[str, float] = {}
_refresh_lock = asyncio.Lock()
_screener_task: Optional[asyncio.Task] = None

VERDICT_LABELS = {
    'buy': 'Đáng mua',
    'hold': 'Giữ',
    'sell': 'Nên bán',
}


def _is_fresh(symbol: str) -> bool:
    sym = symbol.upper()
    ts = _cache_ts.get(sym)
    if ts is None:
        return False
    return time.monotonic() - ts < settings.screener_cache_seconds


async def screen_symbol(symbol: str) -> Dict[str, Any]:
    from app.services.coin_agent_orchestrator import orchestrator

    sym = symbol.strip().upper()
    try:
        result = await orchestrator.run_coin_pipeline(sym, user_holdings=0.0)
        decision = result.get('decision') or {}
        verdict = str(decision.get('verdict', 'hold'))
        score = float(decision.get('score', 0))
        extra = decision.get('extra') or {}
        buy_votes = int(extra.get('buy_agents', 0))
        return {
            'ai_verdict': verdict,
            'ai_confidence': round(score * 100, 1),
            'ai_buy_votes': buy_votes,
            'ai_sell_votes': int(extra.get('sell_agents', 0)),
            'ai_hold_votes': int(extra.get('hold_agents', 0)),
            'ai_label': VERDICT_LABELS.get(verdict, verdict),
            'is_buy_pick': verdict == 'buy',
            'screened_at': result.get('timestamp'),
        }
    except Exception:
        return {
            'ai_verdict': 'hold',
            'ai_confidence': 0.0,
            'ai_buy_votes': 0,
            'ai_sell_votes': 0,
            'ai_hold_votes': 0,
            'ai_label': '',
            'is_buy_pick': False,
        }


def get_signal(symbol: str) -> Optional[Dict[str, Any]]:
    return _signal_cache.get(symbol.strip().upper())


def attach_signals(watchlist: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in watchlist:
        item = dict(row)
        sym = str(item.get('symbol', '')).upper()
        sig = _signal_cache.get(sym)
        if sig:
            item.update(sig)
        else:
            item.setdefault('ai_verdict', 'pending')
            item.setdefault('ai_label', '')
            item.setdefault('is_buy_pick', False)
        out.append(item)
    return out


def get_all_signals() -> Dict[str, Dict[str, Any]]:
    return dict(_signal_cache)


async def refresh_symbol(symbol: str, *, force: bool = False) -> Dict[str, Any]:
    sym = symbol.strip().upper()
    if not force and _is_fresh(sym) and sym in _signal_cache:
        return _signal_cache[sym]
    sig = await screen_symbol(sym)
    _signal_cache[sym] = sig
    _cache_ts[sym] = time.monotonic()
    return sig


async def refresh_all_signals(*, force: bool = False) -> None:
    from app.services.watchlist_store import get_effective_watchlist

    symbols = get_effective_watchlist()
    sem = asyncio.Semaphore(2)

    async def _one(sym: str) -> None:
        if not force and _is_fresh(sym):
            return
        async with sem:
            await refresh_symbol(sym, force=True)
            await asyncio.sleep(0.5)

    async with _refresh_lock:
        await asyncio.gather(*[_one(s) for s in symbols])

    try:
        from app.services.market_ws import notify_market_update

        await notify_market_update()
    except Exception:
        pass


async def request_signal_refresh(symbol: Optional[str] = None) -> None:
    if symbol:
        await refresh_symbol(symbol, force=True)
        try:
            from app.services.market_ws import notify_market_update

            await notify_market_update()
        except Exception:
            pass
    else:
        asyncio.create_task(refresh_all_signals(force=False))


async def _screener_loop() -> None:
    await asyncio.sleep(8)
    while True:
        try:
            await refresh_all_signals()
        except Exception:
            pass
        await asyncio.sleep(settings.screener_refresh_seconds)


def start_screener() -> None:
    global _screener_task
    if _screener_task is None or _screener_task.done():
        _screener_task = asyncio.create_task(_screener_loop())
