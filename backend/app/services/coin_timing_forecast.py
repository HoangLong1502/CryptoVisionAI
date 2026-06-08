"""AI buy/sell timing windows and price targets from technical + committee context."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional


def _round_price(v: float) -> float:
    if v <= 0:
        return 0.0
    if v >= 1000:
        return round(v, 2)
    if v >= 1:
        return round(v, 4)
    return round(v, 6)


def _fmt_date(dt: datetime) -> str:
    return dt.strftime('%Y-%m-%d')


def _fmt_usd(v: float) -> str:
    if v >= 1000:
        return f'${v:,.2f}'
    if v >= 1:
        return f'${v:.4f}'
    return f'${v:.6f}'


def _window_label(start: datetime, end: datetime) -> str:
    days = max(1, (end - start).days)
    if days <= 3:
        return 'Within 1–3 days'
    if days <= 7:
        return 'Within 1 week'
    if days <= 14:
        return 'Within 2 weeks'
    if days <= 30:
        return f'~{days} days ({days // 7}–{(days + 6) // 7} weeks)'
    weeks = days // 7
    return f'~{weeks}–{weeks + 2} weeks'


def build_timing_forecast(
    symbol: str,
    *,
    verdict: str,
    holdings: float,
    coin_detail: Optional[Dict[str, Any]] = None,
    historical_analysis: Optional[Dict[str, Any]] = None,
    indicators: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Estimate buy window, sell window, and target prices (model-based, not advice)."""
    sym = symbol.upper()
    verdict = str(verdict or 'hold').lower()
    detail = coin_detail or {}
    hist = historical_analysis or {}
    ind = indicators or {}

    price = float((detail.get('prices') or {}).get('last') or ind.get('current_price') or 0)
    sr = hist.get('support_resistance') or {}
    support = float(sr.get('support') or (price * 0.92 if price else 0))
    resistance = float(sr.get('resistance') or (price * 1.08 if price else 0))
    if price <= 0:
        price = float(sr.get('current_price') or support or 1)

    sma20 = float(ind.get('sma20') or price)
    atr_pct = float((hist.get('volatility') or {}).get('atr_percent') or 3.0)
    condition = (hist.get('overbought_oversold') or {}).get('condition', 'neutral')
    trend_dir = (hist.get('trend') or {}).get('direction', 'sideways')
    r30 = float((hist.get('momentum') or {}).get('return_30d') or 0)
    dist_support = float(sr.get('distance_to_support_pct') or 5)

    now = datetime.now(timezone.utc)

    # --- Buy window ---
    if verdict == 'sell':
        buy_start = now + timedelta(days=21)
        buy_end = now + timedelta(days=45)
        buy_recommended = False
        entry_low = _round_price(support)
        entry_high = _round_price(min(sma20, price * 0.97))
        entry_ideal = _round_price((entry_low + entry_high) / 2 if entry_high else entry_low)
        buy_note = (
            f'Committee is cautious on {sym}. Wait for a pullback toward support '
            f'({_fmt_usd(entry_low)}) before considering an entry.'
        )
    elif condition == 'oversold' or dist_support <= 3:
        buy_start = now
        buy_end = now + timedelta(days=5)
        buy_recommended = verdict == 'buy'
        entry_low = _round_price(support)
        entry_high = _round_price(min(price, sma20 * 1.01))
        entry_ideal = _round_price(min(price, (support + price) / 2))
        buy_note = (
            f'Price is near support ({_fmt_usd(support)}). '
            f'Favorable zone to scale in between {_fmt_usd(entry_low)} – {_fmt_usd(entry_high)}.'
        )
    elif condition == 'overbought' or trend_dir == 'downtrend':
        buy_start = now + timedelta(days=7)
        buy_end = now + timedelta(days=21)
        buy_recommended = verdict == 'buy'
        entry_low = _round_price(support)
        entry_high = _round_price(sma20)
        entry_ideal = _round_price((support + sma20) / 2)
        buy_note = (
            f'Wait for a dip toward support/SMA20. '
            f'Target entry {_fmt_usd(entry_ideal)} (range {_fmt_usd(entry_low)} – {_fmt_usd(entry_high)}).'
        )
    elif verdict == 'buy':
        buy_start = now
        buy_end = now + timedelta(days=10)
        buy_recommended = True
        entry_low = _round_price(min(support, price * 0.985))
        entry_high = _round_price(price * 1.01)
        entry_ideal = _round_price(price * 0.995)
        buy_note = (
            f'BUY signal active — DCA between {_fmt_usd(entry_low)} and {_fmt_usd(entry_high)} '
            f'over the next ~10 days.'
        )
    else:
        buy_start = now + timedelta(days=5)
        buy_end = now + timedelta(days=14)
        buy_recommended = False
        entry_low = _round_price(support)
        entry_high = _round_price(price)
        entry_ideal = _round_price((support + price) / 2)
        buy_note = (
            f'No strong buy signal. Watch for entry near {_fmt_usd(entry_ideal)} if trend improves.'
        )

    # --- Sell window & targets ---
    vol_factor = 1.0 if atr_pct > 5 else 0.7 if atr_pct > 2.5 else 0.5
    hold_days = int(14 + (30 * vol_factor))
    if trend_dir == 'uptrend' and r30 > 5:
        hold_days = max(10, hold_days - 7)
    elif trend_dir == 'downtrend':
        hold_days = max(7, hold_days - 5)

    if verdict == 'sell' and holdings > 0:
        sell_start = now
        sell_end = now + timedelta(days=max(3, hold_days // 2))
        sell_note = (
            f'You hold {sym} and the committee leans SELL. '
            f'Consider exiting between {_fmt_usd(price * 0.99)} and resistance.'
        )
    elif verdict == 'sell':
        sell_start = now + timedelta(days=hold_days)
        sell_end = now + timedelta(days=hold_days + 21)
        sell_note = f'If you entered later, plan exit near resistance after the trend stabilizes.'
    else:
        sell_start = now + timedelta(days=hold_days)
        sell_end = now + timedelta(days=hold_days + max(14, int(21 * vol_factor)))
        sell_note = (
            f'Estimated hold period ~{hold_days} days based on volatility and trend. '
            f'Take profit near projected resistance zone.'
        )

    move_pct = max(2.0, min(25.0, abs(r30) * 0.6 + atr_pct * 1.5))
    if trend_dir == 'uptrend':
        move_pct = max(move_pct, 4.0)
    elif trend_dir == 'downtrend':
        move_pct = min(move_pct, 8.0)

    target_base = _round_price(resistance)
    target_low = _round_price(max(entry_ideal, resistance * 0.97, price * (1 + move_pct / 200)))
    target_high = _round_price(
        max(
            resistance,
            price * (1 + move_pct / 100),
            resistance + (resistance - support) * 0.35,
        ),
    )
    if target_high < target_base:
        target_high = _round_price(target_base * 1.05)
    if target_low > target_base:
        target_low = _round_price(target_base * 0.98)

    stop_loss = _round_price(support * 0.97)
    ref_entry = entry_ideal if entry_ideal > 0 else price
    expected_gain = round(((target_base - ref_entry) / ref_entry) * 100, 2) if ref_entry else 0

    confidence = 'medium'
    if hist.get('status') != 'ok':
        confidence = 'low'
    elif verdict in ('buy', 'sell') and trend_dir in ('uptrend', 'downtrend'):
        confidence = 'high' if abs(r30) > 3 else 'medium'

    return {
        'symbol': sym,
        'current_price': _round_price(price),
        'buy_window': {
            'start_date': _fmt_date(buy_start),
            'end_date': _fmt_date(buy_end),
            'label': _window_label(buy_start, buy_end),
            'entry_price_low': entry_low,
            'entry_price_high': entry_high,
            'entry_price_ideal': entry_ideal,
            'recommended': buy_recommended,
            'note': buy_note,
        },
        'sell_window': {
            'start_date': _fmt_date(sell_start),
            'end_date': _fmt_date(sell_end),
            'label': _window_label(sell_start, sell_end),
            'target_price_low': target_low,
            'target_price_high': target_high,
            'target_price_base': target_base,
            'stop_loss': stop_loss,
            'expected_gain_pct': expected_gain,
            'note': sell_note,
        },
        'confidence': confidence,
        'methodology': (
            'Combines 60-day support/resistance, volatility (ATR), momentum, RSI/MACD context, '
            'and committee verdict. Crypto trades 24/7 — dates are UTC estimates.'
        ),
        'disclaimer': (
            'Model-based timing and price targets for research only — not financial advice. '
            'Markets can move faster than any forecast.'
        ),
    }
