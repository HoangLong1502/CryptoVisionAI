"""In-memory paper trading wallet with optional JSON persistence."""
from __future__ import annotations

import json
import threading
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
    }


def _load_wallet() -> Dict[str, Any]:
    if _wallet_path.is_file():
        try:
            data = json.loads(_wallet_path.read_text(encoding='utf-8'))
            if isinstance(data, dict) and 'cash_usd' in data:
                data.setdefault('initial_balance_usd', settings.paper_trading_initial_balance)
                data.setdefault('holdings', {})
                data.setdefault('trades', [])
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


def buy_coin(symbol: str, amount_usd: float) -> Dict[str, Any]:
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
        holdings: Dict[str, Dict[str, float]] = wallet.setdefault('holdings', {})
        pos = holdings.get(sym) or {'quantity': 0.0, 'avg_buy_price': 0.0}
        old_qty = float(pos.get('quantity') or 0)
        old_avg = float(pos.get('avg_buy_price') or 0)
        new_qty = old_qty + qty
        new_avg = ((old_qty * old_avg) + amount) / new_qty if new_qty > 0 else price

        holdings[sym] = {'quantity': new_qty, 'avg_buy_price': new_avg}
        wallet['cash_usd'] = cash - amount
        wallet.setdefault('trades', []).append({
            'side': 'buy',
            'symbol': sym,
            'quantity': round(qty, 8),
            'price': round(price, 8),
            'amount_usd': round(amount, 2),
        })
        _save_wallet(wallet)

    snap = get_wallet_snapshot()
    return {
        'ok': True,
        'message': f'Bought {qty:.8f} {sym} @ ${price:,.4f}',
        'trade': {'side': 'buy', 'symbol': sym, 'quantity': round(qty, 8), 'price': price, 'amount_usd': round(amount, 2)},
        'wallet': snap,
    }


def sell_coin(symbol: str, quantity: Optional[float] = None, sell_all: bool = False) -> Dict[str, Any]:
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
        remaining = held - qty
        if remaining <= 1e-10:
            holdings.pop(sym, None)
        else:
            holdings[sym] = {
                'quantity': remaining,
                'avg_buy_price': float(pos.get('avg_buy_price') or 0),
            }

        wallet['cash_usd'] = float(wallet.get('cash_usd') or 0) + proceeds
        wallet.setdefault('trades', []).append({
            'side': 'sell',
            'symbol': sym,
            'quantity': round(qty, 8),
            'price': round(price, 8),
            'amount_usd': round(proceeds, 2),
        })
        _save_wallet(wallet)

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
    return {'ok': True, 'message': 'Paper wallet reset', 'wallet': get_wallet_snapshot()}
