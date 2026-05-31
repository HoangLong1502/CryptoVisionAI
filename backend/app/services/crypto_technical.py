"""Technical indicators for crypto OHLC series."""
from __future__ import annotations

from typing import Any, Dict, List


def calculate_rsi(closes: List[float], period: int = 14) -> Dict[str, Any]:
    if len(closes) < period + 1:
        return {'rsi': 50.0, 'signal': 'neutral'}
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
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


def calculate_macd(closes: List[float]) -> Dict[str, Any]:
    if len(closes) < 26:
        return {'crossover_signal': 'neutral', 'histogram': 0}

    def ema(data: List[float], span: int) -> List[float]:
        k = 2 / (span + 1)
        out = [data[0]]
        for x in data[1:]:
            out.append(x * k + out[-1] * (1 - k))
        return out

    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    macd_line = [a - b for a, b in zip(ema12, ema26)]
    signal_line = ema(macd_line, 9)
    hist = macd_line[-1] - signal_line[-1]
    prev_hist = macd_line[-2] - signal_line[-2] if len(macd_line) > 1 else 0
    if hist > 0 and prev_hist <= 0:
        cross = 'bullish_cross'
    elif hist < 0 and prev_hist >= 0:
        cross = 'bearish_cross'
    elif hist > 0:
        cross = 'bullish'
    else:
        cross = 'bearish'
    return {'crossover_signal': cross, 'histogram': round(hist, 4)}


def calculate_volume_profile(prices: List[Dict[str, Any]]) -> Dict[str, Any]:
    vols = [float(p.get('volume') or 0) for p in prices[-20:]]
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


async def calculate_all_indicators(prices: List[Dict[str, Any]]) -> Dict[str, Any]:
    closes = [float(p['close']) for p in prices if p.get('close')]
    if len(closes) < 5:
        return {}
    rsi = calculate_rsi(closes)
    macd = calculate_macd(closes)
    vol = calculate_volume_profile(prices)
    sma20 = sum(closes[-20:]) / min(20, len(closes))
    sma50 = sum(closes[-50:]) / min(50, len(closes)) if len(closes) >= 10 else sma20
    current = closes[-1]
    return {
        'rsi': rsi,
        'macd': macd,
        'volume': vol,
        'sma20': round(sma20, 4),
        'sma50': round(sma50, 4),
        'current_price': round(current, 4),
        'trend': 'uptrend' if sma20 > sma50 else 'downtrend' if sma20 < sma50 * 0.98 else 'sideways',
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
    hi = max(closes[-30:]) if len(closes) >= 30 else max(closes)
    lo = min(closes[-30:]) if len(closes) >= 30 else min(closes)
    pos = ((closes[-1] - lo) / (hi - lo) * 100) if hi > lo else 50
    if pos >= 80:
        condition = 'overbought'
    elif pos <= 20:
        condition = 'oversold'
    else:
        condition = 'neutral'
    returns = [(closes[i] / closes[i - 1] - 1) for i in range(1, len(closes))]
    import statistics
    vol_pct = statistics.stdev(returns[-20:]) * 100 if len(returns) >= 5 else 2.0
    return {
        'status': 'ok',
        'trend': {'direction': direction, 'strength': min(1.0, abs(r10) / 20)},
        'momentum': {'momentum': momentum, 'score': score, 'return_5d': round(r5, 2), 'return_10d': round(r10, 2), 'return_30d': round(r30, 2)},
        'overbought_oversold': {'condition': condition, 'normalized_position': round(pos, 1)},
        'volatility': {'atr_percent': round(vol_pct, 2), 'level': 'high' if vol_pct > 5 else 'medium' if vol_pct > 2.5 else 'low'},
        'support_resistance': {
            'support': round(lo, 4),
            'resistance': round(hi, 4),
            'current_price': round(closes[-1], 4),
            'distance_to_support_pct': round((closes[-1] - lo) / closes[-1] * 100, 2) if closes[-1] else 0,
            'distance_to_resistance_pct': round((hi - closes[-1]) / closes[-1] * 100, 2) if closes[-1] else 0,
        },
    }
