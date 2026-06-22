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
        'risk_halted': False,
        'risk_halt_reason': None,
        'risk_halted_at': None,
        'cooldowns': {},
        'recent_actions': [],
        'stats': {'total_buys': 0, 'total_sells': 0, 'cycles': 0, 'stop_losses': 0},
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
                base.setdefault('stats', {'total_buys': 0, 'total_sells': 0, 'cycles': 0, 'stop_losses': 0})
                base.setdefault('risk_halted', False)
                base.setdefault('risk_halt_reason', None)
                base.setdefault('risk_halted_at', None)
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


def _risk_settings() -> Dict[str, Any]:
    return {
        'max_deploy_pct': settings.auto_trade_max_deploy_pct,
        'max_position_pct': settings.auto_trade_max_position_pct,
        'stop_loss_pct': settings.auto_trade_stop_loss_pct,
        'stop_loss_usd': settings.auto_trade_stop_loss_usd,
        'max_drawdown_pct': settings.auto_trade_max_drawdown_pct,
        'min_profit_usd': settings.auto_trade_min_profit_usd,
    }


def _wallet_risk_metrics(wallet: Dict[str, Any]) -> Dict[str, Any]:
    initial = float(wallet.get('initial_balance_usd') or settings.paper_trading_initial_balance)
    equity = float(wallet.get('total_equity_usd') or 0)
    cash = float(wallet.get('cash_usd') or 0)
    invested = float(wallet.get('holdings_value_usd') or 0)
    pnl = equity - initial
    drawdown_pct = max(0.0, (initial - equity) / initial * 100) if initial > 0 else 0.0
    deploy_pct = invested / equity if equity > 0 else 0.0
    room_deploy_usd = max(0.0, equity * settings.auto_trade_max_deploy_pct - invested)
    return {
        'initial_balance_usd': round(initial, 2),
        'total_equity_usd': round(equity, 2),
        'cash_usd': round(cash, 2),
        'invested_usd': round(invested, 2),
        'deploy_pct': round(deploy_pct * 100, 2),
        'drawdown_pct': round(drawdown_pct, 2),
        'pnl_usd': round(pnl, 2),
        'room_deploy_usd': round(min(room_deploy_usd, cash), 2),
        'at_drawdown_limit': drawdown_pct >= settings.auto_trade_max_drawdown_pct,
    }


def _position_stop_loss_triggered(row: Dict[str, Any]) -> bool:
    pnl_usd = float(row.get('pnl_usd') or 0)
    pnl_pct = float(row.get('pnl_pct') or 0)
    if pnl_pct <= -abs(settings.auto_trade_stop_loss_pct):
        return True
    min_usd = float(settings.auto_trade_stop_loss_usd or 0)
    if min_usd > 0 and pnl_usd <= -min_usd:
        return True
    return False


def _cap_buy_allocations(
    allocations: Dict[str, float],
    wallet: Dict[str, Any],
    held: Dict[str, Dict[str, Any]],
) -> Dict[str, float]:
    """Clamp buys to deploy cap and per-position upper limit."""
    metrics = _wallet_risk_metrics(wallet)
    equity = float(metrics['total_equity_usd'])
    room = float(metrics['room_deploy_usd'])
    max_pos = equity * settings.auto_trade_max_position_pct

    capped: Dict[str, float] = {}
    budget_left = room
    for sym, amount in sorted(allocations.items(), key=lambda x: -x[1]):
        if budget_left < 1:
            break
        existing = float((held.get(sym) or {}).get('value_usd') or 0)
        pos_room = max(0.0, max_pos - existing)
        amt = min(float(amount), budget_left, pos_room)
        amt = round(amt, 2)
        if amt >= 1:
            capped[sym] = amt
            budget_left = round(budget_left - amt, 2)
    return capped


def _halt_for_risk(state: Dict[str, Any], reason: str) -> None:
    state['enabled'] = False
    state['risk_halted'] = True
    state['risk_halt_reason'] = reason
    state['risk_halted_at'] = _utc_now()
    state['last_error'] = reason


def get_status() -> Dict[str, Any]:
    from app.services.paper_trading import get_wallet_snapshot

    with _state_lock:
        state = _load_state()
    wallet = get_wallet_snapshot()
    metrics = _wallet_risk_metrics(wallet)
    return {
        'enabled': bool(state.get('enabled')),
        'risk_halted': bool(state.get('risk_halted')),
        'risk_halt_reason': state.get('risk_halt_reason'),
        'risk_halted_at': state.get('risk_halted_at'),
        'last_run_at': state.get('last_run_at'),
        'last_error': state.get('last_error'),
        'recent_actions': list(state.get('recent_actions') or [])[:10],
        'stats': dict(state.get('stats') or {}),
        'risk': metrics,
        'settings': {
            'interval_ms': settings.auto_trade_interval_ms,
            'interval_seconds': settings.auto_trade_interval_ms / 1000.0,
            'cooldown_seconds': settings.auto_trade_cooldown_seconds,
            'budget_mode': 'agent_capped_cash',
            **_risk_settings(),
        },
    }


def set_enabled(enabled: bool) -> Dict[str, Any]:
    from app.services.paper_trading import get_wallet_snapshot

    blocked_msg: Optional[str] = None
    with _state_lock:
        state = _load_state()
        if enabled:
            wallet = get_wallet_snapshot()
            metrics = _wallet_risk_metrics(wallet)
            if metrics['at_drawdown_limit']:
                blocked_msg = (
                    f'Drawdown {metrics["drawdown_pct"]:.1f}% ≥ giới hạn '
                    f'{settings.auto_trade_max_drawdown_pct:.1f}% — reset ví hoặc chờ hồi phục'
                )
                state['last_error'] = blocked_msg
                _save_state(state)
            else:
                state['last_error'] = None
                state['risk_halted'] = False
                state['risk_halt_reason'] = None
                state['enabled'] = True
                _save_state(state)
        else:
            state['enabled'] = False
            _save_state(state)

    if blocked_msg:
        status['ok'] = False
        status['message'] = blocked_msg
    else:
        _ensure_loop()
    return status


async def _ai_signal(symbol: str, holdings: float = 0.0) -> Dict[str, Any]:
    from app.services.coin_screener import get_signal, screen_symbol

    if holdings <= 0:
        cached = get_signal(symbol)
        if cached and cached.get('ai_verdict') not in (None, 'pending', ''):
            return cached
    return await screen_symbol(symbol, holdings=holdings)


async def run_cycle(*, force: bool = False) -> Dict[str, Any]:
    """One auto-trading pass: risk checks, stop-loss, take profit, AI sells, capped buys."""
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
            metrics = _wallet_risk_metrics(wallet)

            if metrics['at_drawdown_limit']:
                held = {h['symbol']: h for h in wallet.get('holdings', [])}
                for sym in list(held.keys()):
                    try:
                        res = sell_coin(
                            sym,
                            sell_all=True,
                            source='auto',
                            reason=(
                                f'Circuit breaker · drawdown {metrics["drawdown_pct"]:.1f}% '
                                f'≥ {settings.auto_trade_max_drawdown_pct:.1f}%'
                            ),
                        )
                        actions.append({
                            'side': 'sell',
                            'symbol': sym,
                            'amount_usd': res['trade']['amount_usd'],
                            'message': res['message'],
                            'reason': 'circuit_breaker',
                        })
                    except ValueError as e:
                        actions.append({'side': 'sell', 'symbol': sym, 'skipped': True, 'error': str(e)})

                reason = (
                    f'Dừng bot: drawdown {metrics["drawdown_pct"]:.1f}% vượt giới hạn '
                    f'{settings.auto_trade_max_drawdown_pct:.1f}%'
                )
                with _state_lock:
                    state = _load_state()
                    _halt_for_risk(state, reason)
                    for act in actions:
                        if not act.get('skipped'):
                            _log_action(state, act)
                            state['stats']['total_sells'] = int(state['stats'].get('total_sells', 0)) + 1
                    _save_state(state)
                return {'ok': False, 'halted': True, 'reason': reason, 'actions': actions}

            held = {h['symbol']: h for h in wallet.get('holdings', [])}
            min_profit = float(settings.auto_trade_min_profit_usd)

            for sym, row in list(held.items()):
                qty = float(row.get('quantity') or 0)
                if qty <= 0:
                    continue

                pnl_usd = float(row.get('pnl_usd') or 0)
                pnl_pct = float(row.get('pnl_pct') or 0)

                if _position_stop_loss_triggered(row):
                    reason = (
                        f'Stop-loss · {pnl_pct:+.1f}% (${pnl_usd:+.2f}) '
                        f'≤ -{settings.auto_trade_stop_loss_pct:.1f}%'
                    )
                    try:
                        res = sell_coin(sym, sell_all=True, source='auto', reason=reason)
                        action = {
                            'side': 'sell',
                            'symbol': sym,
                            'amount_usd': res['trade']['amount_usd'],
                            'message': res['message'],
                            'reason': 'stop_loss',
                            'pnl_usd': round(pnl_usd, 2),
                            'pnl_pct': round(pnl_pct, 2),
                        }
                        actions.append(action)
                        with _state_lock:
                            state = _load_state()
                            _log_action(state, action)
                            state['stats']['total_sells'] = int(state['stats'].get('total_sells', 0)) + 1
                            state['stats']['stop_losses'] = int(state['stats'].get('stop_losses', 0)) + 1
                            _save_state(state)
                    except ValueError as e:
                        actions.append({'side': 'sell', 'symbol': sym, 'skipped': True, 'error': str(e)})
                    continue

                if pnl_usd >= min_profit:
                    reason = f'Take profit · +${pnl_usd:.2f} unrealized (min ${min_profit:.2f})'
                    try:
                        res = sell_coin(sym, sell_all=True, source='auto', reason=reason)
                        action = {
                            'side': 'sell',
                            'symbol': sym,
                            'amount_usd': res['trade']['amount_usd'],
                            'message': res['message'],
                            'reason': 'take_profit',
                            'pnl_usd': round(pnl_usd, 2),
                        }
                        actions.append(action)
                        with _state_lock:
                            state = _load_state()
                            _log_action(state, action)
                            state['stats']['total_sells'] = int(state['stats'].get('total_sells', 0)) + 1
                            _save_state(state)
                    except ValueError as e:
                        actions.append({'side': 'sell', 'symbol': sym, 'skipped': True, 'error': str(e)})
                    continue

                with _state_lock:
                    state = _load_state()
                    if _on_cooldown(state, sym):
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
            held_map = {h['symbol']: h for h in wallet.get('holdings', [])}
            metrics = _wallet_risk_metrics(wallet)
            cash = float(metrics['room_deploy_usd'])

            if cash >= 1 and not metrics['at_drawdown_limit']:
                candidates: List[Dict[str, Any]] = []
                for sym in get_effective_watchlist():
                    if sym in held_syms:
                        continue
                    with _state_lock:
                        state = _load_state()
                        if _on_cooldown(state, sym):
                            continue
                    sig = await _ai_signal(sym, holdings=0.0)
                    if str(sig.get('ai_verdict')) == 'buy' or sig.get('is_buy_pick'):
                        row = {'symbol': sym, **sig}
                        candidates.append(row)

                if candidates:
                    from app.services.coin_agent_orchestrator import orchestrator

                    plan = await orchestrator.suggest_buy_allocations(
                        candidates,
                        cash,
                    )
                    plan_rationale = str(plan.get('rationale') or '')
                    allocations = _cap_buy_allocations(
                        plan.get('allocations') or {},
                        get_wallet_snapshot(),
                        held_map,
                    )

                    for sym, amount in allocations.items():
                        wallet = get_wallet_snapshot()
                        cash_now = float(_wallet_risk_metrics(wallet)['room_deploy_usd'])
                        amount = round(float(amount), 2)

                        if amount < 1:
                            actions.append({
                                'side': 'buy',
                                'symbol': sym,
                                'skipped': True,
                                'error': 'Agent skipped — below $1 minimum',
                            })
                            continue
                        if amount > cash_now:
                            actions.append({
                                'side': 'buy',
                                'symbol': sym,
                                'skipped': True,
                                'error': f'Risk cap: need ${amount:.2f}, room ${cash_now:.2f}',
                            })
                            continue

                        sig = next((c for c in candidates if c.get('symbol') == sym), {})
                        conf = sig.get('ai_confidence', 0)
                        reason = f'AI BUY · ${amount:.2f} · {plan_rationale[:120]}'
                        try:
                            res = buy_coin(sym, amount, source='auto', reason=reason)
                            action = {
                                'side': 'buy',
                                'symbol': sym,
                                'amount_usd': res['trade']['amount_usd'],
                                'message': res['message'],
                                'ai_verdict': 'buy',
                                'ai_confidence': conf,
                                'allocation_rationale': plan_rationale,
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
