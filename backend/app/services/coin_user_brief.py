"""User-facing debate summary with portfolio context."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.crypto_technical import calculate_volume_profile

VERDICT_LABELS = {
    'buy': 'Consider BUY',
    'sell': 'Consider SELL',
    'hold': 'WATCH / HOLD',
}

AGENT_LABELS = {
    'MarketScanner': 'Market Scanner',
    'OnChainAnalyst': 'On-Chain Analyst',
    'TechnicalAnalyst': 'Technical Analyst',
    'SentimentAnalysis': 'Sentiment Analyst',
    'RiskManagement': 'Risk Manager',
    'PortfolioAdvisor': 'Portfolio Advisor',
    'DecisionMaker': 'Committee Chair',
}

VERDICT_SHORT = {'buy': 'Buy', 'sell': 'Sell', 'hold': 'Hold'}


def build_coin_user_brief(
    symbol: str,
    agent_results: Dict[str, Any],
    *,
    coin_detail: Optional[Dict[str, Any]] = None,
    historical_analysis: Optional[Dict[str, Any]] = None,
    prices: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    sym = symbol.upper()
    decision = agent_results.get('decision', {}) or {}
    verdict = str(decision.get('verdict', 'hold')).lower()
    extra = decision.get('extra', {}) or {}
    holdings = float(agent_results.get('user_holdings') or 0)
    price = float((coin_detail or {}).get('prices', {}).get('last') or 0)
    position_usd = holdings * price

    insights: List[Dict[str, Any]] = []
    hist = historical_analysis or {}

    if holdings <= 0:
        insights.append({
            'category': 'portfolio',
            'title': 'Your position',
            'text': f'You do not hold {sym}. The committee evaluates whether to open a new position.',
            'tone': 'neutral',
        })
    else:
        insights.append({
            'category': 'portfolio',
            'title': 'Your position',
            'text': f'Holding {holdings} {sym} (~${position_usd:,.2f} USD). Recommendations apply to your current portfolio.',
            'tone': 'neutral',
        })

    if coin_detail:
        vol = float(coin_detail.get('volume_24h') or 0)
        mcap = float(coin_detail.get('market_cap') or 0)
        vtm = float(coin_detail.get('volume_to_mcap_pct') or 0)
        flow = (coin_detail.get('order_flow') or {}).get('pressure_label', '')
        insights.append({
            'category': 'liquidity',
            'title': '24h trading volume',
            'text': f'Volume ${vol/1e6:.1f}M — {vtm:.1f}% of market cap (${mcap/1e9:.2f}B). {flow}'.strip(),
            'tone': 'positive' if vtm > 8 else 'neutral',
        })

    if hist.get('status') == 'ok':
        trend = hist['trend']['direction']
        mom = hist['momentum']
        tone = 'positive' if trend == 'uptrend' else 'warning' if trend == 'downtrend' else 'neutral'
        insights.append({
            'category': 'trend',
            'title': f'60-day trend: {trend}',
            'text': f"5d: {mom['return_5d']:+.1f}%, 30d: {mom['return_30d']:+.1f}%.",
            'tone': tone,
        })

    if prices:
        vol_profile = calculate_volume_profile(prices)
        if vol_profile['trend'] == 'spike':
            insights.append({
                'category': 'volume',
                'title': 'Volume spike',
                'text': f"Volume is {vol_profile['volume_ratio']}× the average — watch which side dominates.",
                'tone': 'warning',
            })

    buy_v = int(extra.get('buy_agents', 0))
    sell_v = int(extra.get('sell_agents', 0))
    hold_v = int(extra.get('hold_agents', 0))
    insights.append({
        'category': 'consensus',
        'title': 'Committee session',
        'text': f'{buy_v} BUY · {hold_v} HOLD · {sell_v} SELL — consensus: {verdict.upper()}.',
        'tone': 'positive' if verdict == 'buy' else 'warning' if verdict == 'sell' else 'neutral',
    })

    verdict_label = VERDICT_LABELS.get(verdict, VERDICT_LABELS['hold'])
    tone = 'positive' if verdict == 'buy' else 'warning' if verdict == 'sell' else 'neutral'

    if holdings <= 0 and verdict == 'buy':
        action = 'Consider a small starter position with DCA — set stop-loss below the nearest support.'
    elif holdings <= 0 and verdict == 'sell':
        action = 'Avoid buying for now — stay on the sidelines and monitor.'
    elif holdings > 0 and verdict == 'sell':
        action = 'Consider trimming or taking profit / cutting losses depending on your goals.'
    elif holdings > 0 and verdict == 'buy':
        action = 'You may hold and add a small amount if you accept crypto volatility risk.'
    else:
        action = 'Hold your current position and wait for clearer signals.' if holdings > 0 else 'Watch and wait — no entry needed yet.'

    agent_lines = []
    for ag in agent_results.get('agents', []):
        if ag.get('agent') == 'DecisionMaker':
            continue
        name = ag.get('agent', '')
        v = str(ag.get('verdict', 'hold')).lower()
        agent_lines.append({
            'agent': name,
            'agent_label': AGENT_LABELS.get(name, name),
            'verdict_label': VERDICT_SHORT.get(v, v),
            'one_liner': str(ag.get('rationale', ''))[:160],
        })

    headline = f'{sym} — {verdict_label}'
    if holdings > 0:
        headline = f'{sym} (holding {holdings}) — {verdict_label}'

    return {
        'symbol': sym,
        'user_holdings': holdings,
        'position_value_usd': round(position_usd, 2),
        'headline': headline,
        'verdict': verdict,
        'verdict_label': verdict_label,
        'verdict_tone': tone,
        'summary': (
            f'Crypto committee analyzed {sym} with a position of {holdings} coins. '
            f'Conclusion: {verdict_label}. {buy_v} buy, {sell_v} sell.'
        ),
        'action': action,
        'insights': insights,
        'warnings': [i['title'] for i in insights if i['tone'] == 'warning'][:5],
        'positives': [i['title'] for i in insights if i['tone'] == 'positive'][:5],
        'agent_lines': agent_lines,
        'votes': {'buy': buy_v, 'hold': hold_v, 'sell': sell_v},
    }
