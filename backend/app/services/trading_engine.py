"""
PRO rule-based trading engine — institutional-style decision pipeline.

Pipeline: Regime → Liquidity → Structure → Trend → Volume → Momentum
          → Volatility → Candles → Confidence → Risk Filter → Decision

Survival > Consistency > Profit. Long-only for paper wallet; bearish = sell/hold.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.services.crypto_technical import (
    _ema_series,
    _sma,
    calculate_atr,
    calculate_macd,
    calculate_rsi,
)

# Layer weights (sum = 1.0)
_W = {
    'regime': 0.25,
    'structure': 0.20,
    'liquidity': 0.15,
    'trend': 0.10,
    'volume': 0.10,
    'momentum': 0.05,
    'volatility': 0.05,
    'candlestick': 0.05,
    'risk_filter': 0.05,
}

MIN_CONFIDENCE = 60
MIN_ENTRY_CONFIDENCE = 70
MIN_ADX = 15
MIN_RR = 2.0


def _bars_from_prices(prices: List[Dict[str, Any]]) -> List[Dict[str, float]]:
    """Derive OHLC from close-only daily series (CoinGecko)."""
    bars: List[Dict[str, float]] = []
    prev = None
    for p in prices:
        c = float(p.get('close') or 0)
        if c <= 0:
            continue
        o = prev if prev is not None else c
        h = max(o, c)
        l = min(o, c)
        bars.append({
            'open': o,
            'high': h,
            'low': l,
            'close': c,
            'volume': float(p.get('volume') or 0),
        })
        prev = c
    return bars


def _calculate_adx(bars: List[Dict[str, float]], period: int = 14) -> Dict[str, Any]:
    if len(bars) < period + 2:
        return {'adx': 0.0, 'plus_di': 0.0, 'minus_di': 0.0}

    plus_dm: List[float] = []
    minus_dm: List[float] = []
    tr_list: List[float] = []

    for i in range(1, len(bars)):
        up = bars[i]['high'] - bars[i - 1]['high']
        down = bars[i - 1]['low'] - bars[i]['low']
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
        tr = max(
            bars[i]['high'] - bars[i]['low'],
            abs(bars[i]['high'] - bars[i - 1]['close']),
            abs(bars[i]['low'] - bars[i - 1]['close']),
        )
        tr_list.append(tr)

    if len(tr_list) < period:
        return {'adx': 0.0, 'plus_di': 0.0, 'minus_di': 0.0}

    atr = sum(tr_list[:period]) / period
    p_dm = sum(plus_dm[:period]) / period
    m_dm = sum(minus_dm[:period]) / period

    dx_vals: List[float] = []
    for i in range(period, len(tr_list)):
        atr = (atr * (period - 1) + tr_list[i]) / period
        p_dm = (p_dm * (period - 1) + plus_dm[i]) / period
        m_dm = (m_dm * (period - 1) + minus_dm[i]) / period
        if atr <= 0:
            continue
        pdi = 100 * p_dm / atr
        mdi = 100 * m_dm / atr
        denom = pdi + mdi
        dx = abs(pdi - mdi) / denom * 100 if denom > 0 else 0
        dx_vals.append(dx)

    if not dx_vals:
        return {'adx': 0.0, 'plus_di': 0.0, 'minus_di': 0.0}

    adx = sum(dx_vals[-period:]) / min(period, len(dx_vals[-period:]))
    pdi = 100 * p_dm / atr if atr > 0 else 0
    mdi = 100 * m_dm / atr if atr > 0 else 0
    return {'adx': round(adx, 2), 'plus_di': round(pdi, 2), 'minus_di': round(mdi, 2)}


def _bollinger(closes: List[float], period: int = 20, mult: float = 2.0) -> Dict[str, Any]:
    if len(closes) < period:
        return {'upper': 0, 'middle': 0, 'lower': 0, 'width_pct': 0, 'position': 50}
    window = closes[-period:]
    mid = sum(window) / period
    variance = sum((x - mid) ** 2 for x in window) / period
    std = variance ** 0.5
    upper = mid + mult * std
    lower = mid - mult * std
    width = ((upper - lower) / mid * 100) if mid > 0 else 0
    price = closes[-1]
    pos = ((price - lower) / (upper - lower) * 100) if upper > lower else 50
    return {
        'upper': round(upper, 4),
        'middle': round(mid, 4),
        'lower': round(lower, 4),
        'width_pct': round(width, 2),
        'position': round(pos, 1),
    }


def _swing_points(closes: List[float], left: int = 2, right: int = 2) -> Tuple[List[int], List[int]]:
    highs: List[int] = []
    lows: List[int] = []
    for i in range(left, len(closes) - right):
        seg = closes[i - left: i + right + 1]
        if closes[i] == max(seg):
            highs.append(i)
        if closes[i] == min(seg):
            lows.append(i)
    return highs, lows


def _analyze_structure(closes: List[float]) -> Dict[str, Any]:
    highs, lows = _swing_points(closes)
    if len(highs) < 2 or len(lows) < 2:
        return {
            'bias': 'unclear',
            'pattern': 'insufficient_swings',
            'score': 40,
            'event': None,
            'hh': False,
            'hl': False,
            'lh': False,
            'll': False,
        }

    h1, h2 = closes[highs[-2]], closes[highs[-1]]
    l1, l2 = closes[lows[-2]], closes[lows[-1]]
    hh = h2 > h1
    hl = l2 > l1
    lh = h2 < h1
    ll = l2 < l1

    price = closes[-1]
    last_high = closes[highs[-1]]
    last_low = closes[lows[-1]]

    event = None
    if hh and hl:
        bias = 'bullish'
        score = 85
        if price > last_high:
            event = 'BOS_bull'
            score = 92
    elif lh and ll:
        bias = 'bearish'
        score = 15
        if price < last_low:
            event = 'BOS_bear'
            score = 8
    elif hh and ll:
        bias = 'unclear'
        score = 45
        event = 'CHOCH'
    elif lh and hl:
        bias = 'sideways'
        score = 50
        event = 'CHOCH'
    else:
        bias = 'sideways'
        score = 48

    return {
        'bias': bias,
        'pattern': f"{'HH' if hh else 'LH'}+{'HL' if hl else 'LL'}",
        'score': score,
        'event': event,
        'hh': hh,
        'hl': hl,
        'lh': lh,
        'll': ll,
        'last_swing_high': round(last_high, 4),
        'last_swing_low': round(last_low, 4),
    }


def _analyze_liquidity(bars: List[Dict[str, float]], closes: List[float]) -> Dict[str, Any]:
    if len(bars) < 10:
        return {'score': 45, 'signals': [], 'liquidity_sweep': False, 'fvg': False}

    signals: List[str] = []
    score = 50.0
    highs, lows = _swing_points(closes)
    tol = 0.003

    if len(highs) >= 2:
        h_a, h_b = closes[highs[-2]], closes[highs[-1]]
        if abs(h_a - h_b) / max(h_a, 1e-9) < tol:
            signals.append('equal_highs')
            score -= 8

    if len(lows) >= 2:
        l_a, l_b = closes[lows[-2]], closes[lows[-1]]
        if abs(l_a - l_b) / max(l_a, 1e-9) < tol:
            signals.append('equal_lows')
            score += 6

    liquidity_sweep = False
    if len(bars) >= 5:
        recent_hi = max(b['high'] for b in bars[-6:-1])
        recent_lo = min(b['low'] for b in bars[-6:-1])
        last = bars[-1]
        if last['high'] > recent_hi and last['close'] < recent_hi:
            signals.append('sweep_high_reversal')
            liquidity_sweep = True
            score += 12
        if last['low'] < recent_lo and last['close'] > recent_lo:
            signals.append('sweep_low_reversal')
            liquidity_sweep = True
            score += 14

    fvg = False
    if len(bars) >= 3:
        b0, b1, b2 = bars[-3], bars[-2], bars[-1]
        if b2['low'] > b0['high']:
            signals.append('bullish_fvg')
            fvg = True
            score += 10
        elif b2['high'] < b0['low']:
            signals.append('bearish_fvg')
            score -= 10

    return {
        'score': max(0, min(100, score)),
        'signals': signals,
        'liquidity_sweep': liquidity_sweep,
        'fvg': fvg,
    }


def _candlestick_score(bars: List[Dict[str, float]]) -> Dict[str, Any]:
    if len(bars) < 3:
        return {'score': 50, 'patterns': []}

    patterns: List[str] = []
    score = 50.0
    c = bars[-1]
    p = bars[-2]
    body = abs(c['close'] - c['open'])
    range_ = c['high'] - c['low']
    if range_ <= 0:
        return {'score': 50, 'patterns': []}

    lower_wick = min(c['open'], c['close']) - c['low']
    upper_wick = c['high'] - max(c['open'], c['close'])

    if lower_wick > body * 2 and upper_wick < body * 0.5 and c['close'] > c['open']:
        patterns.append('hammer')
        score += 12
    if upper_wick > body * 2 and lower_wick < body * 0.5 and c['close'] < c['open']:
        patterns.append('shooting_star')
        score -= 12

    pb = abs(p['close'] - p['open'])
    if (
        c['close'] > c['open']
        and p['close'] < p['open']
        and c['open'] <= p['close']
        and c['close'] >= p['open']
        and body > pb
    ):
        patterns.append('bullish_engulfing')
        score += 15
    if (
        c['close'] < c['open']
        and p['close'] > p['open']
        and c['open'] >= p['close']
        and c['close'] <= p['open']
        and body > pb
    ):
        patterns.append('bearish_engulfing')
        score -= 15

    if len(bars) >= 3:
        b2 = bars[-3]
        mid = b2['close'] < b2['open']
        small = abs(p['close'] - p['open']) < abs(b2['close'] - b2['open']) * 0.4
        strong_up = c['close'] > c['open'] and c['close'] > b2['open']
        if mid and small and strong_up:
            patterns.append('morning_star')
            score += 14

    return {'score': max(0, min(100, score)), 'patterns': patterns}


def _detect_regime(
    closes: List[float],
    price: float,
    adx: float,
    atr_pct: float,
    atr_expanding: bool,
    vol_ratio: float,
) -> Dict[str, Any]:
    ema50 = _ema_series(closes, 50)[-1] if len(closes) >= 50 else None
    ema200 = _ema_series(closes, 200)[-1] if len(closes) >= 50 else _ema_series(closes, min(len(closes), 100))[-1]

    score = 50.0
    regime = 'unclear'
    action = 'hold_only'

    bullish_stack = ema50 is not None and ema200 is not None and ema50 > ema200 and price > ema50
    bearish_stack = ema50 is not None and ema200 is not None and ema50 < ema200 and price < ema50

    if adx >= 25 and bullish_stack:
        regime = 'strong_bull' if adx >= 30 else 'weak_bull'
        score = 88 if regime == 'strong_bull' else 72
        action = 'long_only'
    elif adx >= 25 and bearish_stack:
        regime = 'strong_bear' if adx >= 30 else 'weak_bear'
        score = 12 if regime == 'strong_bear' else 28
        action = 'short_only'
    elif adx < 20:
        regime = 'sideways'
        score = 48
        action = 'mean_reversion_only'
    else:
        regime = 'transition'
        score = 42
        action = 'hold_only'

    if atr_pct > 5 or (atr_expanding and vol_ratio > 1.4):
        regime = f'{regime}_high_vol' if regime != 'unclear' else 'high_volatility'
        score = max(0, score - 10)
    elif atr_pct < 2:
        regime = f'{regime}_low_vol' if 'sideways' in regime else regime
        score += 4

    return {
        'regime': regime,
        'action': action,
        'score': max(0, min(100, score)),
        'adx': adx,
        'ema50': round(ema50, 4) if ema50 else None,
        'ema200': round(ema200, 4) if ema200 else None,
        'bullish_stack': bullish_stack,
        'bearish_stack': bearish_stack,
    }


def evaluate_trading_engine(
    prices: List[Dict[str, Any]],
    *,
    change_pct_24h: float = 0.0,
) -> Dict[str, Any]:
    """
    Full PRO pipeline. Returns decision + confidence 0–100 + layer breakdown.
    """
    bars = _bars_from_prices(prices)
    closes = [b['close'] for b in bars]

    if len(closes) < 30:
        return _empty_result(['insufficient_history'])

    price = closes[-1]
    rsi = calculate_rsi(closes)
    macd = calculate_macd(closes)
    atr_info = calculate_atr(prices)
    adx_info = _calculate_adx(bars)
    adx = float(adx_info['adx'])
    bb = _bollinger(closes)

    atr_series = []
    for i in range(15, len(prices)):
        sub = calculate_atr(prices[: i + 1])
        atr_series.append(sub['atr_percent'])
    atr_expanding = len(atr_series) >= 2 and atr_series[-1] > atr_series[-2] * 1.08

    vols = [b['volume'] for b in bars]
    vol_ma20 = sum(vols[-20:]) / min(20, len(vols[-20:])) if vols else 0
    vol_ratio = (vols[-1] / vol_ma20) if vol_ma20 > 0 else 1.0

    regime = _detect_regime(closes, price, adx, atr_info['atr_percent'], atr_expanding, vol_ratio)
    structure = _analyze_structure(closes)
    liquidity = _analyze_liquidity(bars, closes)
    candles = _candlestick_score(bars)

    ema20 = _ema_series(closes, 20)[-1]
    ema50 = _ema_series(closes, 50)[-1] if len(closes) >= 50 else None
    ema200 = _ema_series(closes, min(200, len(closes)))[-1]

    trend_score = 0.0
    if ema20 and ema50 and ema20 > ema50:
        trend_score += 10
    if ema50 and ema200 and ema50 > ema200:
        trend_score += 20
    if ema200 and price > ema200:
        trend_score += 15
    if adx > 25:
        trend_score += 15
    trend_score = min(60, trend_score)
    trend_layer = trend_score / 60 * 100

    if vol_ratio >= 1.5:
        vol_layer = 85
    elif vol_ratio >= 1.0:
        vol_layer = 65
    else:
        vol_layer = 35

    rsi_val = float(rsi.get('rsi') or 50)
    mom_layer = 50.0
    if 50 <= rsi_val <= 70:
        mom_layer += 15
    elif 30 <= rsi_val < 50:
        mom_layer += 5
    elif rsi_val > 70:
        mom_layer -= 20
    elif rsi_val < 30:
        mom_layer += 10
    macd_cross = str(macd.get('crossover_signal', ''))
    if macd_cross == 'bullish_cross':
        mom_layer += 10
    elif macd_cross == 'bearish_cross':
        mom_layer -= 10
    hist = float(macd.get('histogram') or 0)
    if hist > 0:
        mom_layer += 5
    else:
        mom_layer -= 5
    mom_layer = max(0, min(100, mom_layer))

    atr_pct = float(atr_info['atr_percent'])
    if atr_pct < 2.5:
        volat_layer = 70
        vol_strategy = 'range'
    elif atr_pct <= 5:
        volat_layer = 60
        vol_strategy = 'trend_follow'
    else:
        volat_layer = 35
        vol_strategy = 'breakout_reduced_size'

    window = min(30, len(closes))
    support = min(closes[-window:])
    resistance = max(closes[-window:])
    dist_sup = (price - support) / price * 100 if price else 0
    dist_res = (resistance - price) / price * 100 if price else 0
    risk_reward = (dist_res / dist_sup) if dist_sup > 0.3 else 0

    risk_layer = 50.0
    reject: List[str] = []
    if risk_reward >= MIN_RR and dist_res > 1.5:
        risk_layer += 25
    elif risk_reward < MIN_RR:
        risk_layer -= 20
        reject.append('risk_reward_below_2')
    if dist_res < 1.0:
        risk_layer -= 15
        reject.append('resistance_too_close')
    if adx < MIN_ADX:
        risk_layer -= 20
        reject.append('adx_too_low')
    if vol_ratio < 0.85:
        risk_layer -= 15
        reject.append('volume_too_low')
    risk_layer = max(0, min(100, risk_layer))

    layers = {
        'regime': regime['score'],
        'structure': float(structure['score']),
        'liquidity': float(liquidity['score']),
        'trend': trend_layer,
        'volume': vol_layer,
        'momentum': mom_layer,
        'volatility': volat_layer,
        'candlestick': float(candles['score']),
        'risk_filter': risk_layer,
    }

    confidence = sum(layers[k] * _W[k] for k in _W)
    confidence = round(max(0, min(100, confidence)), 1)

    veto_reasons: List[str] = list(reject)

    if regime['bearish_stack'] and adx >= 20:
        veto_reasons.append('bearish_regime')
    if structure['bias'] == 'bearish' and structure.get('event') == 'BOS_bear':
        veto_reasons.append('bearish_structure_break')
    if rsi_val > 75 and dist_res < 2:
        veto_reasons.append('overbought_at_resistance')
    if change_pct_24h > 15 and rsi_val > 70:
        veto_reasons.append('parabolic_pump')
    if vol_ratio < 0.7 and change_pct_24h > 3:
        veto_reasons.append('low_volume_breakout_invalid')
    if confidence < MIN_CONFIDENCE:
        veto_reasons.append('confidence_below_60')

    hard_veto_keys = {
        'overbought_at_resistance', 'parabolic_pump', 'low_volume_breakout_invalid',
        'confidence_below_60', 'bearish_regime', 'bearish_structure_break',
    }
    veto = regime['action'] == 'short_only' or any(r in hard_veto_keys for r in veto_reasons)

    long_entry = (
        not veto
        and confidence >= MIN_ENTRY_CONFIDENCE
        and regime['action'] in ('long_only', 'mean_reversion_only')
        and structure['bias'] in ('bullish', 'sideways')
        and structure.get('hh') and structure.get('hl')
        and vol_ratio >= 1.0
        and mom_layer >= 50
        and risk_reward >= MIN_RR
        and adx >= MIN_ADX
    )

    if regime['action'] == 'mean_reversion_only':
        long_entry = (
            not veto
            and confidence >= MIN_ENTRY_CONFIDENCE
            and rsi_val <= 38
            and liquidity.get('liquidity_sweep')
            and dist_sup < 3
        )

    if long_entry:
        decision = 'buy'
    elif (
        structure['bias'] == 'bearish'
        or regime['bearish_stack']
        or (confidence < 40 and structure.get('event') == 'BOS_bear')
    ):
        decision = 'sell'
    else:
        decision = 'hold'

    if veto and decision == 'buy':
        decision = 'hold'

    if confidence >= 75 and not veto:
        quality = 'strong'
    elif confidence >= MIN_ENTRY_CONFIDENCE and not veto:
        quality = 'moderate'
    elif confidence >= MIN_CONFIDENCE:
        quality = 'weak'
    else:
        quality = 'avoid'

    confluence = sum(1 for v in layers.values() if v >= 60)
    pos_factor = 0.5 if 'high_vol' in regime['regime'] else 1.0
    if vol_strategy == 'breakout_reduced_size':
        pos_factor = min(pos_factor, 0.6)

    stop_loss = max(support, price * (1 - atr_pct / 100 * 2))
    take_profit = resistance

    return {
        'decision': decision,
        'confidence': confidence,
        'quality': quality,
        'veto': veto,
        'veto_reasons': veto_reasons,
        'reject_reasons': reject,
        'confluence': confluence,
        'score': round(confidence / 100, 4),
        'regime': regime['regime'],
        'regime_action': regime['action'],
        'structure_bias': structure['bias'],
        'structure_event': structure.get('event'),
        'layers': layers,
        'risk_reward': round(risk_reward, 2),
        'position_size_factor': pos_factor,
        'stop_loss': round(stop_loss, 4),
        'take_profit': round(take_profit, 4),
        'adx': adx,
        'volume_ratio': round(vol_ratio, 2),
        'rsi': rsi_val,
        'bullish': liquidity.get('signals', []) + candles.get('patterns', []),
        'bearish': [r for r in veto_reasons if r],
        'trend': 'uptrend' if structure['bias'] == 'bullish' else 'downtrend' if structure['bias'] == 'bearish' else 'sideways',
    }


def _empty_result(reasons: List[str]) -> Dict[str, Any]:
    return {
        'decision': 'hold',
        'confidence': 0.0,
        'quality': 'avoid',
        'veto': True,
        'veto_reasons': reasons,
        'reject_reasons': reasons,
        'confluence': 0,
        'score': 0.0,
        'regime': 'unclear',
        'regime_action': 'hold_only',
        'structure_bias': 'unclear',
        'layers': {},
        'risk_reward': 0.0,
        'position_size_factor': 0.0,
        'bullish': [],
        'bearish': reasons,
        'trend': 'sideways',
    }
