"""Technical indicators for crypto OHLC series (Wilder RSI, standard MACD, ATR)."""
from __future__ import annotations

import statistics
from typing import Any, Dict, List, Optional


def _sma(values: List[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def _ema_series(values: List[float], span: int) -> List[float]:
    """Exponential moving average (TradingView / standard MACD seed)."""
    if not values:
        return []
    k = 2 / (span + 1)
    out = [values[0]]
    for x in values[1:]:
        out.append(x * k + out[-1] * (1 - k))
    return out


def calculate_rsi(closes: List[float], period: int = 14) -> Dict[str, Any]:
    """
    Wilder RSI-14 (industry default on most charting platforms).
    First average uses SMA; subsequent values use Wilder smoothing.
    """
    if len(closes) < period + 1:
        return {'rsi': 50.0, 'signal': 'neutral'}

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        rsi = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

    if rsi >= 70:
        signal = 'overbought'
    elif rsi <= 30:
        signal = 'oversold'
    elif rsi >= 55:
        signal = 'bullish'
    elif rsi <= 45:
        signal = 'bearish'
    else:
        signal = 'neutral'
    return {'rsi': round(rsi, 2), 'signal': signal}


def calculate_macd(
    closes: List[float],
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> Dict[str, Any]:
    """
    MACD (12, 26, 9): EMA crossover of MACD line vs signal line.
    """
    if len(closes) < slow + signal_period:
        return {
            'macd_line': 0.0,
            'signal_line': 0.0,
            'histogram': 0.0,
            'crossover_signal': 'neutral',
        }

    ema_fast = _ema_series(closes, fast)
    ema_slow = _ema_series(closes, slow)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line = _ema_series(macd_line, signal_period)

    macd_val = macd_line[-1]
    signal_val = signal_line[-1]
    hist = macd_val - signal_val
    prev_macd = macd_line[-2]
    prev_signal = signal_line[-2]

    if macd_val > signal_val and prev_macd <= prev_signal:
        cross = 'bullish_cross'
    elif macd_val < signal_val and prev_macd >= prev_signal:
        cross = 'bearish_cross'
    elif hist > 0:
        cross = 'bullish'
    else:
        cross = 'bearish'

    return {
        'macd_line': round(macd_val, 6),
        'signal_line': round(signal_val, 6),
        'histogram': round(hist, 6),
        'crossover_signal': cross,
    }


def calculate_atr(prices: List[Dict[str, Any]], period: int = 14) -> Dict[str, Any]:
    """
    Wilder ATR from close series (CoinGecko daily data has no H/L).
    True range approximated as |close - prev_close|.
    """
    closes = [float(p['close']) for p in prices if p.get('close')]
    if len(closes) < period + 1:
        return {'atr': 0.0, 'atr_percent': 0.0, 'level': 'medium'}

    true_ranges = [abs(closes[i] - closes[i - 1]) for i in range(1, len(closes))]
    atr = sum(true_ranges[:period]) / period
    for tr in true_ranges[period:]:
        atr = (atr * (period - 1) + tr) / period

    price = closes[-1]
    atr_pct = (atr / price * 100) if price > 0 else 0.0
    level = 'high' if atr_pct > 5 else 'medium' if atr_pct > 2.5 else 'low'
    return {
        'atr': round(atr, 6),
        'atr_percent': round(atr_pct, 2),
        'level': level,
    }


def calculate_volume_profile(prices: List[Dict[str, Any]], lookback: int = 20) -> Dict[str, Any]:
    vols = [float(p.get('volume') or 0) for p in prices[-lookback:]]
    if not vols:
        return {'trend': 'normal', 'volume_ratio': 1.0, 'current_volume': 0, 'avg_volume': 0}
    avg = sum(vols[:-1]) / max(len(vols) - 1, 1) if len(vols) > 1 else vols[0]
    cur = vols[-1]
    ratio = cur / avg if avg > 0 else 1.0
    if ratio >= 1.5:
        trend = 'spike'
    elif ratio < 0.7:
        trend = 'below_average'
    elif ratio > 1.1:
        trend = 'above_average'
    else:
        trend = 'normal'
    return {
        'trend': trend,
        'volume_ratio': round(ratio, 2),
        'current_volume': int(cur),
        'avg_volume': int(avg),
    }


def _trend_from_mas(closes: List[float], sma20: Optional[float], sma50: Optional[float]) -> str:
    if sma20 is not None and sma50 is not None:
        if sma20 > sma50 * 1.002:
            return 'uptrend'
        if sma20 < sma50 * 0.998:
            return 'downtrend'
        return 'sideways'
    if sma20 is not None:
        return 'uptrend' if closes[-1] > sma20 else 'downtrend'
    return 'sideways'


async def calculate_all_indicators(prices: List[Dict[str, Any]]) -> Dict[str, Any]:
    closes = [float(p['close']) for p in prices if p.get('close')]
    if len(closes) < 5:
        return {}

    rsi = calculate_rsi(closes)
    macd = calculate_macd(closes)
    vol = calculate_volume_profile(prices)
    atr = calculate_atr(prices)
    sma20 = _sma(closes, 20)
    sma50 = _sma(closes, 50)
    current = closes[-1]

    return {
        'rsi': rsi,
        'macd': macd,
        'volume': vol,
        'atr': atr,
        'sma20': round(sma20, 4) if sma20 is not None else None,
        'sma50': round(sma50, 4) if sma50 is not None else None,
        'current_price': round(current, 4),
        'trend': _trend_from_mas(closes, sma20, sma50),
    }


async def full_historical_analysis(symbol: str, prices: List[Dict[str, Any]]) -> Dict[str, Any]:
    if len(prices) < 10:
        return {'status': 'no_data'}

    closes = [float(p['close']) for p in prices]
    n = len(closes)
    r5 = ((closes[-1] / closes[-6]) - 1) * 100 if n >= 6 else 0
    r10 = ((closes[-1] / closes[-11]) - 1) * 100 if n >= 11 else 0
    r30 = ((closes[-1] / closes[-31]) - 1) * 100 if n >= 31 else 0

    indicators = await calculate_all_indicators(prices)
    direction = indicators.get('trend', 'sideways')

    if r5 > 3 and r10 > 0:
        momentum = 'strong_bullish'
        score = 0.7
    elif r5 > 0:
        momentum = 'bullish'
        score = 0.55
    elif r5 < -3 and r10 < 0:
        momentum = 'strong_bearish'
        score = -0.7
    elif r5 < 0:
        momentum = 'bearish'
        score = -0.55
    else:
        momentum = 'neutral'
        score = 0.0

    # 30-day Donchian channel (classic S/R on daily chart)
    window = min(30, n)
    hi = max(closes[-window:])
    lo = min(closes[-window:])
    pos = ((closes[-1] - lo) / (hi - lo) * 100) if hi > lo else 50
    if pos >= 80:
        condition = 'overbought'
    elif pos <= 20:
        condition = 'oversold'
    else:
        condition = 'neutral'

    atr_info = calculate_atr(prices)
    returns = [(closes[i] / closes[i - 1] - 1) for i in range(1, len(closes))]
    return_vol = statistics.stdev(returns[-20:]) * 100 if len(returns) >= 5 else atr_info['atr_percent']

    return {
        'status': 'ok',
        'trend': {'direction': direction, 'strength': min(1.0, abs(r10) / 20)},
        'momentum': {
            'momentum': momentum,
            'score': score,
            'return_5d': round(r5, 2),
            'return_10d': round(r10, 2),
            'return_30d': round(r30, 2),
        },
        'overbought_oversold': {'condition': condition, 'normalized_position': round(pos, 1)},
        'volatility': {
            'atr': atr_info['atr'],
            'atr_percent': atr_info['atr_percent'],
            'return_volatility_pct': round(return_vol, 2),
            'level': atr_info['level'],
        },
        'support_resistance': {
            'support': round(lo, 4),
            'resistance': round(hi, 4),
            'current_price': round(closes[-1], 4),
            'distance_to_support_pct': round((closes[-1] - lo) / closes[-1] * 100, 2) if closes[-1] else 0,
            'distance_to_resistance_pct': round((hi - closes[-1]) / closes[-1] * 100, 2) if closes[-1] else 0,
        },
    }


def score_buy_setup(
    indicators: Dict[str, Any],
    hist: Dict[str, Any],
    *,
    change_pct_24h: float = 0.0,
    prices: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Legacy wrapper — delegates to PRO trading engine when prices are available."""
    if prices and len(prices) >= 30:
        from app.services.trading_engine import evaluate_trading_engine

        return evaluate_trading_engine(prices, change_pct_24h=change_pct_24h)
    return {
        'score': 0.0,
        'confidence': 0.0,
        'quality': 'avoid',
        'veto': True,
        'veto_reasons': ['insufficient_data'],
        'confluence': 0,
        'bullish': [],
        'bearish': [],
        'risk_reward': 0.0,
        'decision': 'hold',
    }
