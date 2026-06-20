"""Paper auto-trading — buy/sell from AI committee signals using the virtual wallet."""
from __future__ import annotations

import asyncio
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings

_state_lock = threading.Lock()
_state_path = Path(settings.auto_trading_state_path)
_loop_task: Optional[asyncio.Task] = None
_cycle_lock = asyncio.Lock()


def _default_state() -> Dict[str, Any]:
    return {
        'enabled': False,
        'last_run_at': None,
        'last_error': None,
        'cooldowns': {},
        'recent_actions': [],
        'stats': {'total_buys': 0, 'total_sells': 0, 'cycles': 0},
    }


def _load_state() -> Dict[str, Any]:
    if _state_path.is_file():
        try:
            data = json.loads(_state_path.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                base = _default_state()
                base.update(data)
                base.setdefault('cooldowns', {})
                base.setdefault('recent_actions', [])
                base.setdefault('stats', {'total_buys': 0, 'total_sells': 0, 'cycles': 0})
                return base
        except (json.JSONDecodeError, OSError, TypeError):
            pass
    return _default_state()


def _save_state(state: Dict[str, Any]) -> None:
    _state_path.parent.mkdir(parents=True, exist_ok=True)
    _state_path.write_text(json.dumps(state, indent=2), encoding='utf-8')


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_action(state: Dict[str, Any], action: Dict[str, Any]) -> None:
    action['at'] = _utc_now()
    recent: List[Dict[str, Any]] = state.setdefault('recent_actions', [])
    recent.insert(0, action)
    state['recent_actions'] = recent[:30]
    sym = str(action.get('symbol', '')).upper()
    if sym:
        state.setdefault('cooldowns', {})[sym] = time.monotonic()


def _on_cooldown(state: Dict[str, Any], symbol: str) -> bool:
    sym = symbol.upper()
    ts = state.get('cooldowns', {}).get(sym)
    if ts is None:
        return False
    return time.monotonic() - float(ts) < settings.auto_trade_cooldown_seconds


def get_status() -> Dict[str, Any]:
    with _state_lock:
        state = _load_state()
    return {
        'enabled': bool(state.get('enabled')),
        'last_run_at': state.get('last_run_at'),
        'last_error': state.get('last_error'),
        'recent_actions': list(state.get('recent_actions') or [])[:10],
        'stats': dict(state.get('stats') or {}),
        'settings': {
            'interval_ms': settings.auto_trade_interval_ms,
            'interval_seconds': settings.auto_trade_interval_ms / 1000.0,
            'buy_usd': settings.auto_trade_buy_usd,
            'max_positions': settings.auto_trade_max_positions,
            'max_cash_pct': settings.auto_trade_max_cash_pct,
            'cooldown_seconds': settings.auto_trade_cooldown_seconds,
        },
    }


def set_enabled(enabled: bool) -> Dict[str, Any]:
    with _state_lock:
        state = _load_state()
        state['enabled'] = enabled
        if enabled:
            state['last_error'] = None
        _save_state(state)
    _ensure_loop()
    return get_status()


async def _ai_signal(symbol: str, holdings: float = 0.0) -> Dict[str, Any]:
    from app.services.coin_screener import get_signal, screen_symbol

    if holdings <= 0:
        cached = get_signal(symbol)
        if cached and cached.get('ai_verdict') not in (None, 'pending', ''):
            return cached
    return await screen_symbol(symbol, holdings=holdings)


async def run_cycle(*, force: bool = False) -> Dict[str, Any]:
    """One auto-trading pass: sell AI-sell picks, then buy AI-buy picks."""
    from app.services.paper_trading import buy_coin, get_wallet_snapshot, sell_coin
    from app.services.watchlist_store import get_effective_watchlist

    with _state_lock:
        state = _load_state()
        if not force and not state.get('enabled'):
            return {'ok': False, 'message': 'Auto-trading is off', 'actions': []}

    async with _cycle_lock:
        actions: List[Dict[str, Any]] = []

        try:
            wallet = get_wallet_snapshot()
            held = {h['symbol']: h for h in wallet.get('holdings', [])}

            for sym, row in list(held.items()):
                with _state_lock:
                    state = _load_state()
                    if _on_cooldown(state, sym):
                        continue

                qty = float(row.get('quantity') or 0)
                if qty <= 0:
                    continue

                sig = await _ai_signal(sym, holdings=qty)
                if str(sig.get('ai_verdict', 'hold')) != 'sell':
                    continue

                conf = sig.get('ai_confidence', 0)
                reason = f'AI SELL · {conf}% confidence · {sig.get("ai_sell_votes", 0)} sell votes'
                try:
                    res = sell_coin(sym, sell_all=True, source='auto', reason=reason)
                    action = {
                        'side': 'sell',
                        'symbol': sym,
                        'amount_usd': res['trade']['amount_usd'],
                        'message': res['message'],
                        'ai_verdict': 'sell',
                        'ai_confidence': conf,
                    }
                    actions.append(action)
                    with _state_lock:
                        state = _load_state()
                        _log_action(state, action)
                        state['stats']['total_sells'] = int(state['stats'].get('total_sells', 0)) + 1
                        _save_state(state)
                except ValueError as e:
                    actions.append({'side': 'sell', 'symbol': sym, 'skipped': True, 'error': str(e)})

            wallet = get_wallet_snapshot()
            held_syms = {h['symbol'] for h in wallet.get('holdings', [])}
            cash = float(wallet.get('cash_usd') or 0)
            slots = max(0, settings.auto_trade_max_positions - len(held_syms))

            if slots > 0 and cash >= 1:
                candidates: List[tuple[str, Dict[str, Any]]] = []
                for sym in get_effective_watchlist():
                    if sym in held_syms:
                        continue
                    with _state_lock:
                        state = _load_state()
                        if _on_cooldown(state, sym):
                            continue
                    sig = await _ai_signal(sym, holdings=0.0)
                    if str(sig.get('ai_verdict')) == 'buy' or sig.get('is_buy_pick'):
                        candidates.append((sym, sig))

                candidates.sort(key=lambda x: float(x[1].get('ai_confidence') or 0), reverse=True)

                for sym, sig in candidates[:slots]:
                    wallet = get_wallet_snapshot()
                    cash = float(wallet.get('cash_usd') or 0)
                    if cash < 1:
                        break

                    amount = min(
                        settings.auto_trade_buy_usd,
                        cash * settings.auto_trade_max_cash_pct,
                        cash,
                    )
                    if amount < 1:
                        break

                    conf = sig.get('ai_confidence', 0)
                    reason = f'AI BUY · {conf}% confidence · {sig.get("ai_buy_votes", 0)} buy votes'
                    try:
                        res = buy_coin(sym, amount, source='auto', reason=reason)
                        action = {
                            'side': 'buy',
                            'symbol': sym,
                            'amount_usd': res['trade']['amount_usd'],
                            'message': res['message'],
                            'ai_verdict': 'buy',
                            'ai_confidence': conf,
                        }
                        actions.append(action)
                        with _state_lock:
                            state = _load_state()
                            _log_action(state, action)
                            state['stats']['total_buys'] = int(state['stats'].get('total_buys', 0)) + 1
                            _save_state(state)
                    except ValueError as e:
                        actions.append({'side': 'buy', 'symbol': sym, 'skipped': True, 'error': str(e)})

            with _state_lock:
                state = _load_state()
                state['last_run_at'] = _utc_now()
                state['last_error'] = None
                state['stats']['cycles'] = int(state['stats'].get('cycles', 0)) + 1
                _save_state(state)

            if actions:
                try:
                    from app.services.market_ws import notify_market_update

                    await notify_market_update()
                except Exception:
                    pass

            return {'ok': True, 'actions': actions, 'action_count': len([a for a in actions if not a.get('skipped')])}

        except Exception as e:
            with _state_lock:
                state = _load_state()
                state['last_error'] = str(e)
                state['last_run_at'] = _utc_now()
                _save_state(state)
            return {'ok': False, 'error': str(e), 'actions': actions}


async def _auto_loop() -> None:
    await asyncio.sleep(15)
    interval = settings.auto_trade_interval_ms / 1000.0
    while True:
        with _state_lock:
            enabled = bool(_load_state().get('enabled'))
        if enabled and not _cycle_lock.locked():
            try:
                await run_cycle()
            except Exception:
                pass
        await asyncio.sleep(interval)


def _ensure_loop() -> None:
    global _loop_task
    if _loop_task is None or _loop_task.done():
        _loop_task = asyncio.create_task(_auto_loop())


def start_auto_trading_service() -> None:
    _ensure_loop()
