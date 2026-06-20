"""In-memory paper trading wallet with optional JSON persistence."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.binance_realtime import get_live_price
from app.services.crypto_data import _cache

_lock = threading.Lock()
_wallet_path = Path(settings.paper_wallet_path)


def _default_wallet() -> Dict[str, Any]:
    return {
        'cash_usd': float(settings.paper_trading_initial_balance),
        'initial_balance_usd': float(settings.paper_trading_initial_balance),
        'holdings': {},
        'trades': [],
        'realized_pnl': {'auto': 0.0, 'manual': 0.0},
        '_lots_migrated': True,
    }


def _sync_position_from_lots(pos: Dict[str, Any]) -> None:
    lots = pos.get('lots') or []
    qty = sum(float(lot.get('quantity') or 0) for lot in lots)
    if qty <= 0:
        pos['quantity'] = 0.0
        pos['avg_buy_price'] = 0.0
        return
    cost = sum(float(lot.get('quantity') or 0) * float(lot.get('avg_buy_price') or 0) for lot in lots)
    pos['quantity'] = qty
    pos['avg_buy_price'] = cost / qty if qty > 0 else 0.0


def _ensure_lots(wallet: Dict[str, Any]) -> None:
    if wallet.get('_lots_migrated'):
        return
    wallet.setdefault('realized_pnl', {'auto': 0.0, 'manual': 0.0})
    for pos in (wallet.get('holdings') or {}).values():
        if not pos.get('lots'):
            qty = float(pos.get('quantity') or 0)
            if qty > 0:
                pos['lots'] = [{
                    'quantity': qty,
                    'avg_buy_price': float(pos.get('avg_buy_price') or 0),
                    'source': 'manual',
                }]
        _sync_position_from_lots(pos)
    for trade in wallet.get('trades') or []:
        trade.setdefault('source', 'manual')
    wallet['_lots_migrated'] = True


def _load_wallet() -> Dict[str, Any]:
    if _wallet_path.is_file():
        try:
            data = json.loads(_wallet_path.read_text(encoding='utf-8'))
            if isinstance(data, dict) and 'cash_usd' in data:
                data.setdefault('initial_balance_usd', settings.paper_trading_initial_balance)
                data.setdefault('holdings', {})
                data.setdefault('trades', [])
                data.setdefault('realized_pnl', {'auto': 0.0, 'manual': 0.0})
                _ensure_lots(data)
                return data
        except (json.JSONDecodeError, OSError, TypeError):
            pass
    return _default_wallet()


def _save_wallet(wallet: Dict[str, Any]) -> None:
    _wallet_path.parent.mkdir(parents=True, exist_ok=True)
    _wallet_path.write_text(json.dumps(wallet, indent=2), encoding='utf-8')


def _current_price(symbol: str) -> Optional[float]:
    sym = symbol.strip().upper()
    live = get_live_price(sym)
    if live and live > 0:
        return live
    markets = _cache.get('markets') or {}
    row = markets.get(sym) or {}
    price = float(row.get('price') or 0)
    return price if price > 0 else None


def _change_24h_pct(symbol: str) -> float:
    markets = _cache.get('markets') or {}
    row = markets.get(symbol.strip().upper()) or {}
    return float(row.get('change_pct') or row.get('change') or 0)


def _holding_row(symbol: str, qty: float, avg_price: float, price: float) -> Dict[str, Any]:
    cost = qty * avg_price
    value = qty * price
    pnl = value - cost
    pnl_pct = (pnl / cost * 100) if cost > 0 else 0.0
    return {
        'symbol': symbol,
        'quantity': round(qty, 8),
        'avg_buy_price': round(avg_price, 8),
        'current_price': round(price, 8),
        'cost_usd': round(cost, 2),
        'value_usd': round(value, 2),
        'pnl_usd': round(pnl, 2),
        'pnl_pct': round(pnl_pct, 2),
        'change_24h_pct': round(_change_24h_pct(symbol), 2),
    }


def compute_performance_breakdown() -> Dict[str, Any]:
    with _lock:
        wallet = _load_wallet()
        initial = float(wallet.get('initial_balance_usd') or settings.paper_trading_initial_balance)
        half = initial / 2.0
        auto_unreal = manual_unreal = 0.0

        for sym, pos in (wallet.get('holdings') or {}).items():
            price = _current_price(sym)
            if not price:
                price = float(pos.get('avg_buy_price') or 0)
            for lot in pos.get('lots') or []:
                q = float(lot.get('quantity') or 0)
                if q <= 0:
                    continue
                cost = q * float(lot.get('avg_buy_price') or 0)
                val = q * price
                unreal = val - cost
                if lot.get('source') == 'auto':
                    auto_unreal += unreal
                else:
                    manual_unreal += unreal

        realized = wallet.get('realized_pnl') or {}
        auto_realized = float(realized.get('auto') or 0)
        manual_realized = float(realized.get('manual') or 0)
        auto_pnl = auto_realized + auto_unreal
        manual_pnl = manual_realized + manual_unreal
        total_pnl = auto_pnl + manual_pnl

    snap = get_wallet_snapshot()
    return {
        'total_pnl_usd': round(total_pnl, 2),
        'total_pnl_pct': round((total_pnl / initial * 100) if initial > 0 else 0.0, 2),
        'auto_pnl_usd': round(auto_pnl, 2),
        'auto_pnl_pct': round((auto_pnl / half * 100) if half > 0 else 0.0, 2),
        'manual_pnl_usd': round(manual_pnl, 2),
        'manual_pnl_pct': round((manual_pnl / half * 100) if half > 0 else 0.0, 2),
        'total_equity': snap['total_equity_usd'],
        'auto_equity': round(half + auto_pnl, 2),
        'manual_equity': round(half + manual_pnl, 2),
    }


def _record_trade_snapshot() -> None:
    try:
        from app.services.performance_history import record_snapshot

        record_snapshot(force=True)
    except Exception:
        pass


def _apply_sell_lots(
    wallet: Dict[str, Any],
    sym: str,
    pos: Dict[str, Any],
    qty: float,
    price: float,
) -> None:
    remaining = qty
    new_lots: List[Dict[str, Any]] = []
    realized = wallet.setdefault('realized_pnl', {'auto': 0.0, 'manual': 0.0})

    for lot in pos.get('lots') or []:
        if remaining <= 1e-12:
            new_lots.append(lot)
            continue
        lot_qty = float(lot.get('quantity') or 0)
        if lot_qty <= 0:
            continue
        take = min(lot_qty, remaining)
        avg = float(lot.get('avg_buy_price') or 0)
        pnl = take * (price - avg)
        src = lot.get('source') or 'manual'
        realized[src] = float(realized.get(src) or 0) + pnl
        remaining -= take
        left = lot_qty - take
        if left > 1e-10:
            new_lots.append({
                'quantity': left,
                'avg_buy_price': avg,
                'source': src,
            })

    pos['lots'] = new_lots
    _sync_position_from_lots(pos)
    if float(pos.get('quantity') or 0) <= 1e-10:
        wallet.get('holdings', {}).pop(sym, None)


def get_wallet_snapshot() -> Dict[str, Any]:
    with _lock:
        wallet = _load_wallet()
        cash = float(wallet.get('cash_usd') or 0)
        holdings_raw: Dict[str, Dict[str, float]] = wallet.get('holdings') or {}

        holdings: List[Dict[str, Any]] = []
        holdings_value = 0.0
        total_cost = 0.0

        for sym, pos in sorted(holdings_raw.items()):
            qty = float(pos.get('quantity') or 0)
            if qty <= 0:
                continue
            avg = float(pos.get('avg_buy_price') or 0)
            price = _current_price(sym)
            if not price:
                price = avg
            row = _holding_row(sym, qty, avg, price)
            holdings.append(row)
            holdings_value += row['value_usd']
            total_cost += row['cost_usd']

        total_equity = cash + holdings_value
        initial = float(wallet.get('initial_balance_usd') or settings.paper_trading_initial_balance)
        total_pnl = total_equity - initial
        total_pnl_pct = (total_pnl / initial * 100) if initial > 0 else 0.0
        holdings_pnl = holdings_value - total_cost
        holdings_pnl_pct = (holdings_pnl / total_cost * 100) if total_cost > 0 else 0.0

        return {
            'mode': 'paper',
            'cash_usd': round(cash, 2),
            'initial_balance_usd': round(initial, 2),
            'holdings_value_usd': round(holdings_value, 2),
            'total_equity_usd': round(total_equity, 2),
            'total_pnl_usd': round(total_pnl, 2),
            'total_pnl_pct': round(total_pnl_pct, 2),
            'holdings_pnl_usd': round(holdings_pnl, 2),
            'holdings_pnl_pct': round(holdings_pnl_pct, 2),
            'holdings': holdings,
            'trade_count': len(wallet.get('trades') or []),
        }


def get_holding_quantity(symbol: str) -> float:
    sym = symbol.strip().upper()
    with _lock:
        wallet = _load_wallet()
        pos = (wallet.get('holdings') or {}).get(sym) or {}
        return float(pos.get('quantity') or 0)


def buy_coin(
    symbol: str,
    amount_usd: float,
    *,
    source: str = 'manual',
    reason: str = '',
) -> Dict[str, Any]:
    sym = symbol.strip().upper()
    amount = float(amount_usd)
    if amount <= 0:
        raise ValueError('amount_usd must be positive')
    if amount < 1:
        raise ValueError('Minimum buy is $1')

    price = _current_price(sym)
    if not price:
        raise ValueError(f'No live price for {sym}')

    with _lock:
        wallet = _load_wallet()
        cash = float(wallet.get('cash_usd') or 0)
        if amount > cash:
            raise ValueError(f'Insufficient cash: ${cash:.2f} available')

        qty = amount / price
        holdings: Dict[str, Dict[str, Any]] = wallet.setdefault('holdings', {})
        pos = holdings.get(sym) or {'quantity': 0.0, 'avg_buy_price': 0.0, 'lots': []}
        pos.setdefault('lots', []).append({
            'quantity': qty,
            'avg_buy_price': price,
            'source': source,
        })
        _sync_position_from_lots(pos)
        holdings[sym] = pos
        wallet['cash_usd'] = cash - amount
        wallet.setdefault('trades', []).append({
            'side': 'buy',
            'symbol': sym,
            'quantity': round(qty, 8),
            'price': round(price, 8),
            'amount_usd': round(amount, 2),
            'source': source,
            'reason': reason,
        })
        _save_wallet(wallet)

    _record_trade_snapshot()
    snap = get_wallet_snapshot()
    return {
        'ok': True,
        'message': f'Bought {qty:.8f} {sym} @ ${price:,.4f}',
        'trade': {'side': 'buy', 'symbol': sym, 'quantity': round(qty, 8), 'price': price, 'amount_usd': round(amount, 2)},
        'wallet': snap,
    }


def sell_coin(
    symbol: str,
    quantity: Optional[float] = None,
    sell_all: bool = False,
    *,
    source: str = 'manual',
    reason: str = '',
) -> Dict[str, Any]:
    sym = symbol.strip().upper()
    price = _current_price(sym)
    if not price:
        raise ValueError(f'No live price for {sym}')

    with _lock:
        wallet = _load_wallet()
        holdings: Dict[str, Dict[str, float]] = wallet.get('holdings') or {}
        pos = holdings.get(sym)
        if not pos:
            raise ValueError(f'You do not hold any {sym}')

        held = float(pos.get('quantity') or 0)
        if held <= 0:
            raise ValueError(f'You do not hold any {sym}')

        qty = held if sell_all else float(quantity or 0)
        if qty <= 0:
            raise ValueError('quantity must be positive')
        if qty > held + 1e-12:
            raise ValueError(f'Cannot sell {qty} {sym}; you only hold {held}')

        proceeds = qty * price
        _apply_sell_lots(wallet, sym, pos, qty, price)
        wallet['cash_usd'] = float(wallet.get('cash_usd') or 0) + proceeds
        wallet.setdefault('trades', []).append({
            'side': 'sell',
            'symbol': sym,
            'quantity': round(qty, 8),
            'price': round(price, 8),
            'amount_usd': round(proceeds, 2),
            'source': source,
            'reason': reason,
        })
        _save_wallet(wallet)

    _record_trade_snapshot()
    snap = get_wallet_snapshot()
    return {
        'ok': True,
        'message': f'Sold {qty:.8f} {sym} @ ${price:,.4f}',
        'trade': {'side': 'sell', 'symbol': sym, 'quantity': round(qty, 8), 'price': price, 'amount_usd': round(proceeds, 2)},
        'wallet': snap,
    }


def reset_wallet() -> Dict[str, Any]:
    with _lock:
        wallet = _default_wallet()
        _save_wallet(wallet)
    try:
        from app.services.performance_history import record_snapshot

        record_snapshot(force=True)
    except Exception:
        pass
    return {'ok': True, 'message': 'Paper wallet reset', 'wallet': get_wallet_snapshot()}
