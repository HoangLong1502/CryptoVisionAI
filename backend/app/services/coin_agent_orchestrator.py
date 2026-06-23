"""
Crypto investment committee — 5 agents + Chair + Portfolio Advisor (considers user holdings).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.services.crypto_data import (
    build_detail_from_market_row,
    get_coin_detail,
    get_historical_prices,
    sync_market_snapshot,
)
from app.services.watchlist_store import get_effective_watchlist
from app.services.crypto_technical import calculate_all_indicators, full_historical_analysis
from app.services.trading_engine import evaluate_trading_engine

AGENT_ROSTER = [
    {'id': 'MarketScanner', 'role': 'Trend & market liquidity analysis'},
    {'id': 'OnChainAnalyst', 'role': 'Market cap, supply & ecosystem analysis'},
    {'id': 'TechnicalAnalyst', 'role': 'Technical indicators (RSI, MACD, MA)'},
    {'id': 'SentimentAnalysis', 'role': 'Crypto sentiment & price positioning'},
    {'id': 'RiskManagement', 'role': 'Risk management, stop-loss, volatility'},
    {'id': 'PortfolioAdvisor', 'role': 'Portfolio advisor — considers your coin holdings'},
    {'id': 'DecisionMaker', 'role': 'Committee chair — final consensus'},
]


@dataclass
class AgentResult:
    agent: str
    coin_symbol: str
    verdict: str
    score: float
    rationale: str
    extra: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BaseAgent:
    def __init__(self, name: str) -> None:
        self.name = name

    async def evaluate(self, symbol: str, context: Dict[str, Any]) -> AgentResult:
        raise NotImplementedError


class MarketScannerAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__('MarketScanner')

    async def evaluate(self, symbol: str, context: Dict[str, Any]) -> AgentResult:
        hist = context.get('historical_analysis') or {}
        if hist.get('status') == 'no_data':
            return AgentResult(self.name, symbol, 'hold', 0.4, 'Insufficient historical data', {})

        trend = hist['trend']
        mom = hist['momentum']
        sr = hist.get('support_resistance') or {}
        range_pos = float((hist.get('overbought_oversold') or {}).get('normalized_position') or 50)

        score = 0.65 if trend['direction'] == 'uptrend' else 0.35 if trend['direction'] == 'downtrend' else 0.5
        score = score * 0.55 + ((mom['score'] + 1) / 2) * 0.45

        if range_pos >= 85:
            score -= 0.12
        elif range_pos <= 30:
            score += 0.08

        dist_res = float(sr.get('distance_to_resistance_pct') or 0)
        if dist_res < 2 and trend['direction'] != 'uptrend':
            score -= 0.10

        score = max(0.0, min(1.0, score))
        verdict = 'buy' if score >= 0.62 else 'sell' if score <= 0.38 else 'hold'

        detail = context.get('coin_detail') or {}
        vol_pct = detail.get('volume_to_mcap_pct', 0)
        rationale = (
            f"Trend {trend['direction']}, momentum {mom['momentum']}, range {range_pos:.0f}%. "
            f"Volume/mcap ~{vol_pct}%. "
            f"S/R {sr.get('support')}/{sr.get('resistance')}."
        )
        return AgentResult(self.name, symbol, verdict, score, rationale, {'trend': trend['direction']})


class OnChainAnalystAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__('OnChainAnalyst')

    async def evaluate(self, symbol: str, context: Dict[str, Any]) -> AgentResult:
        detail = context.get('coin_detail') or {}
        rank = int(detail.get('rank') or 999)
        mcap = float(detail.get('market_cap') or 0)
        score = 0.75 if rank <= 10 else 0.6 if rank <= 50 else 0.45 if rank <= 200 else 0.35
        if mcap > 10_000_000_000:
            score += 0.05
        score = min(1.0, score)
        verdict = 'buy' if score >= 0.65 else 'sell' if score <= 0.4 else 'hold'
        rationale = (
            f"Market cap rank #{rank}, ~${mcap/1e9:.1f}B. "
            f"{'Blue-chip — strong liquidity' if rank <= 20 else 'Mid/small cap — higher risk'}."
        )
        return AgentResult(self.name, symbol, verdict, score, rationale, {'rank': rank, 'market_cap': mcap})


class TechnicalAnalystAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__('TechnicalAnalyst')

    async def evaluate(self, symbol: str, context: Dict[str, Any]) -> AgentResult:
        indicators = context.get('indicators') or {}
        hist = context.get('historical_analysis') or {}
        if not indicators or hist.get('status') != 'ok':
            return AgentResult(self.name, symbol, 'hold', 0.5, 'Insufficient technical data', {})

        setup = context.get('buy_setup') or {}
        conf = float(setup.get('confidence') or setup.get('score', 0.5) * 100)
        score = conf / 100.0
        quality = setup.get('quality', 'weak')
        engine_decision = setup.get('decision', 'hold')

        if setup.get('veto') or conf < 60:
            verdict = 'hold' if engine_decision != 'sell' else 'sell'
            score = min(score, 0.42)
        elif engine_decision == 'buy' and quality in ('strong', 'moderate') and conf >= 70:
            verdict = 'buy'
        elif engine_decision == 'sell' or conf < 40:
            verdict = 'sell'
        else:
            verdict = 'hold'

        rsi = (indicators.get('rsi') or {}).get('rsi')
        macd = (indicators.get('macd') or {}).get('crossover_signal', 'neutral')
        factors = ', '.join(setup.get('bullish', [])[:3]) or 'none'
        rationale = (
            f"Confluence {setup.get('confluence', 0)} · quality {quality} · "
            f"RSI {rsi}, MACD {macd}. Bullish: {factors}."
        )
        if setup.get('veto_reasons'):
            rationale += f" Veto: {', '.join(setup['veto_reasons'])}."

        return AgentResult(
            self.name, symbol, verdict, score, rationale,
            {'rsi': rsi, 'buy_quality': quality, 'confluence': setup.get('confluence', 0)},
        )


class SentimentAnalysisAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__('SentimentAnalysis')

    async def evaluate(self, symbol: str, context: Dict[str, Any]) -> AgentResult:
        hist = context.get('historical_analysis') or {}
        detail = context.get('coin_detail') or {}
        change = float(detail.get('change_pct') or 0)
        if hist.get('status') == 'no_data':
            score = 0.5 + (0.05 if change > 0 else -0.05)
        else:
            ob = hist['overbought_oversold']
            mom = hist['momentum']
            score = (mom['score'] + 1) / 2
            if ob['condition'] == 'oversold':
                score = min(1.0, score + 0.15)
            elif ob['condition'] == 'overbought':
                score = max(0.0, score - 0.15)
        verdict = 'buy' if score >= 0.6 else 'sell' if score <= 0.4 else 'hold'
        sentiment = 'positive' if score >= 0.6 else 'negative' if score <= 0.4 else 'neutral'
        rationale = f"24h move {change:+.1f}%. Sentiment is {sentiment}."
        return AgentResult(self.name, symbol, verdict, score, rationale, {})


class RiskManagementAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__('RiskManagement')

    async def evaluate(self, symbol: str, context: Dict[str, Any]) -> AgentResult:
        hist = context.get('historical_analysis') or {}
        if hist.get('status') == 'no_data':
            return AgentResult(self.name, symbol, 'hold', 0.5, 'Unable to assess risk', {})
        vol = hist['volatility']
        sr = hist['support_resistance']
        atr = vol['atr_percent']
        score = 0.85 if vol['level'] == 'low' else 0.65 if vol['level'] == 'medium' else 0.4
        verdict = 'buy' if score >= 0.7 else 'sell' if score <= 0.4 else 'hold'
        rationale = (
            f"Volatility {vol['level']} (ATR ~{atr}%). "
            f"Suggested stop-loss: {sr['support']:.2f}. Take-profit: {sr['resistance']:.2f}."
        )
        return AgentResult(
            self.name, symbol, verdict, score, rationale,
            {'risk_level': vol['level'], 'stop_loss': sr['support'], 'take_profit': sr['resistance']},
        )


class PortfolioAdvisorAgent(BaseAgent):
    """Crypto-specific agent — considers user position (may be 0)."""

    def __init__(self) -> None:
        super().__init__('PortfolioAdvisor')

    async def evaluate(self, symbol: str, context: Dict[str, Any]) -> AgentResult:
        holdings = float(context.get('user_holdings') or 0)
        price = float((context.get('coin_detail') or {}).get('prices', {}).get('last') or 0)
        hist = context.get('historical_analysis') or {}
        decision_hint = context.get('preliminary_verdict', 'hold')

        position_value = holdings * price
        if holdings <= 0:
            if decision_hint == 'buy':
                verdict, score = 'buy', 0.72
                rationale = (
                    f"You do not hold {symbol}. The committee sees a buy opportunity — "
                    f"consider a small entry with DCA near support."
                )
            elif decision_hint == 'sell':
                verdict, score = 'hold', 0.55
                rationale = f"You do not hold {symbol} — no need to sell; stay out and observe."
            else:
                verdict, score = 'hold', 0.5
                rationale = f"No {symbol} position yet. Wait for clearer signals before buying."
        else:
            pnl_context = ''
            if hist.get('status') == 'ok':
                r30 = hist['momentum'].get('return_30d', 0)
                pnl_context = f" 30-day trend {r30:+.1f}%."
            if decision_hint == 'sell':
                verdict, score = 'sell', 0.75
                rationale = (
                    f"You hold {holdings} {symbol} (~${position_value:,.2f}). "
                    f"Consider taking profit or cutting losses.{pnl_context}"
                )
            elif decision_hint == 'buy':
                verdict, score = 'buy', 0.68
                rationale = (
                    f"Holding {holdings} {symbol} (~${position_value:,.2f}). "
                    f"May add a small amount if you accept the risk.{pnl_context}"
                )
            else:
                verdict, score = 'hold', 0.6
                rationale = (
                    f"Holding {holdings} {symbol} (~${position_value:,.2f}). "
                    f"No strong signal to add or reduce yet.{pnl_context}"
                )
        return AgentResult(
            self.name, symbol, verdict, score, rationale,
            {'user_holdings': holdings, 'position_value_usd': round(position_value, 2)},
        )


class DecisionMakerAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__('DecisionMaker')

    async def evaluate(self, symbol: str, context: Dict[str, Any]) -> AgentResult:
        history = context.get('history', [])
        if not history:
            return AgentResult(self.name, symbol, 'hold', 0.5, 'No agent data available', {})

        weights = {
            'MarketScanner': 1.0,
            'OnChainAnalyst': 0.9,
            'TechnicalAnalyst': 1.4,
            'SentimentAnalysis': 0.85,
            'RiskManagement': 1.0,
            'PortfolioAdvisor': 1.1,
        }
        core_history = [r for r in history if r['agent'] != 'PortfolioAdvisor']
        weighted = []
        for r in core_history:
            w = weights.get(r['agent'], 1.0)
            weighted.append(r['score'] * w)
        agent_avg = sum(weighted) / len(weighted) if weighted else 0.5

        verdicts = [r['verdict'] for r in core_history]
        buy_c = verdicts.count('buy')
        sell_c = verdicts.count('sell')
        hold_c = verdicts.count('hold')
        consensus = max(buy_c, sell_c, hold_c) / max(len(verdicts), 1)

        setup = context.get('buy_setup') or {}
        setup_score = float(setup.get('confidence') or setup.get('score', 0.5) * 100) / 100.0
        setup_conf = float(setup.get('confidence') or setup_score * 100)
        setup_quality = setup.get('quality', 'weak')
        setup_veto = bool(setup.get('veto'))
        confluence = int(setup.get('confluence', 0))
        engine_decision = setup.get('decision', 'hold')

        tech = next((r for r in core_history if r['agent'] == 'TechnicalAnalyst'), None)
        tech_buy = tech and tech['verdict'] == 'buy'

        final_score = agent_avg * 0.25 + setup_score * 0.75

        if setup_veto or setup_conf < 60:
            verdict = 'sell' if sell_c >= 2 or engine_decision == 'sell' else 'hold'
        elif engine_decision == 'buy' and setup_conf >= 70 and not setup_veto:
            verdict = 'buy'
        elif setup_conf >= 65 and buy_c >= 2 and buy_c > sell_c and tech_buy and engine_decision != 'sell':
            verdict = 'buy'
        elif sell_c >= 2 or engine_decision == 'sell' or setup_conf < 40:
            verdict = 'sell'
        else:
            verdict = 'hold'

        holdings = float(context.get('user_holdings') or 0)
        chair_note = (
            f"Chair: {verdict.upper()} · confluence {confluence} · quality {setup_quality}. "
            f"Votes {buy_c}B/{hold_c}H/{sell_c}S · engine {setup_conf:.0f}/100."
        )
        rationale = chair_note + f" Blended confidence {final_score:.0%}, consensus {consensus:.0%}."
        return AgentResult(
            self.name, symbol, verdict, final_score, rationale,
            {
                'buy_agents': buy_c,
                'sell_agents': sell_c,
                'hold_agents': hold_c,
                'consensus_strength': consensus,
                'user_holdings': holdings,
                'buy_setup_score': setup_conf / 100.0,
                'buy_quality': setup_quality,
                'confluence': confluence,
                'setup_veto': setup_veto,
            },
        )


class CoinAgentOrchestrator:
    def __init__(self) -> None:
        self.market = MarketScannerAgent()
        self.onchain = OnChainAnalystAgent()
        self.technical = TechnicalAnalystAgent()
        self.sentiment = SentimentAnalysisAgent()
        self.risk = RiskManagementAgent()
        self.portfolio = PortfolioAdvisorAgent()
        self.decision = DecisionMakerAgent()

    async def run_coin_pipeline(self, symbol: str, user_holdings: float = 0.0) -> Dict[str, Any]:
        sym = symbol.upper()
        overview = await sync_market_snapshot()
        market_row = next((w for w in overview.get('watchlist', []) if w.get('symbol') == sym), None)
        prices = await get_historical_prices(sym, days=60)
        hist = await full_historical_analysis(sym, prices)
        if market_row:
            detail = build_detail_from_market_row(sym, market_row)
            wl = get_effective_watchlist()
            detail['rank'] = wl.index(sym) + 1 if sym in wl else 0
        else:
            detail = await get_coin_detail(sym)
        indicators = await calculate_all_indicators(prices) if prices else {}
        change_pct = float((detail or {}).get('change_pct') or 0) if detail else 0.0
        buy_setup = evaluate_trading_engine(prices, change_pct_24h=change_pct) if len(prices) >= 30 else {}

        context: Dict[str, Any] = {
            'symbol': sym,
            'user_holdings': max(0.0, float(user_holdings)),
            'historical_analysis': hist,
            'coin_detail': detail or {},
            'indicators': indicators,
            'buy_setup': buy_setup,
            'history': [],
        }

        core_tasks = [
            self.market.evaluate(sym, context),
            self.onchain.evaluate(sym, context),
            self.technical.evaluate(sym, context),
            self.sentiment.evaluate(sym, context),
            self.risk.evaluate(sym, context),
        ]
        core_results = await asyncio.gather(*core_tasks)
        context['history'] = [r.__dict__ for r in core_results]

        pre_votes = [r.verdict for r in core_results]
        if pre_votes.count('buy') > pre_votes.count('sell'):
            context['preliminary_verdict'] = 'buy'
        elif pre_votes.count('sell') > pre_votes.count('buy'):
            context['preliminary_verdict'] = 'sell'
        else:
            context['preliminary_verdict'] = 'hold'

        port = await self.portfolio.evaluate(sym, context)
        context['history'].append(port.__dict__)
        final = await self.decision.evaluate(sym, context)

        return {
            'symbol': sym,
            'user_holdings': context['user_holdings'],
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'agents': context['history'],
            'decision': final.__dict__,
            'buy_setup': buy_setup,
            'coin_detail': detail,
            'historical_prices': prices,
            'historical_analysis': hist,
            'indicators': indicators,
            'workflow': {
                'title': 'Crypto research desk (simulated financial firm)',
                'agents': AGENT_ROSTER,
            },
        }

    async def _risk_multiplier_for(self, symbol: str) -> float:
        """0.5 (high risk) – 1.0 (low risk) from volatility snapshot."""
        try:
            prices = await get_historical_prices(symbol, days=30)
            hist = await full_historical_analysis(symbol, prices)
            if hist.get('status') != 'ok':
                return 0.75
            level = (hist.get('volatility') or {}).get('level', 'medium')
            return {'low': 1.0, 'medium': 0.85, 'high': 0.55}.get(level, 0.75)
        except Exception:
            return 0.75

    async def suggest_buy_allocations(
        self,
        candidates: List[Dict[str, Any]],
        available_cash_usd: float,
    ) -> Dict[str, Any]:
        """
        Portfolio committee sizes buys from up to 100% of available cash.
        All buy candidates may receive a slice; may leave surplus unspent.
        Skips symbols below $1 or when cash is insufficient.
        """
        cash = max(0.0, float(available_cash_usd))
        if cash < 1 or not candidates:
            return {
                'allocations': {},
                'deploy_usd': 0.0,
                'reserve_usd': round(cash, 2),
                'deploy_ratio': 0.0,
                'rationale': 'Không đủ tiền mặt hoặc không có mã đáng mua.',
            }

        picks = sorted(
            candidates,
            key=lambda c: float(c.get('ai_confidence') or 0),
            reverse=True,
        )

        weights: Dict[str, float] = {}
        confidences: List[float] = []
        risk_notes: List[str] = []

        for pick in picks:
            sym = str(pick.get('symbol', '')).upper()
            if not sym:
                continue
            conf = float(pick.get('buy_score') or pick.get('ai_confidence') or 0) / 100.0
            buy_votes = int(pick.get('ai_buy_votes') or 0)
            vote_factor = 0.55 + min(buy_votes, 5) * 0.09
            quality = str(pick.get('buy_quality') or 'moderate')
            quality_mult = {'strong': 1.25, 'moderate': 1.0, 'weak': 0.55, 'avoid': 0.0}.get(quality, 0.8)
            if quality_mult <= 0:
                continue
            risk_mult = await self._risk_multiplier_for(sym)
            confluence = int(pick.get('buy_confluence') or 0)
            conf_mult = 0.85 + min(confluence, 6) * 0.03
            weights[sym] = max(0.01, conf * vote_factor * risk_mult * quality_mult * conf_mult)
            confidences.append(conf)
            risk_notes.append(f'{sym} {quality}×{quality_mult:.2f}')

        if not weights:
            return {
                'allocations': {},
                'deploy_usd': 0.0,
                'reserve_usd': round(cash, 2),
                'deploy_ratio': 0.0,
                'rationale': 'Không có mã hợp lệ để phân bổ.',
            }

        avg_conf = sum(confidences) / len(confidences)
        deploy_ratio = min(0.92, max(0.20, avg_conf * 0.75 + 0.18))
        total_deploy = round(cash * deploy_ratio, 2)
        sum_w = sum(weights.values())

        raw_allocs: Dict[str, float] = {
            sym: total_deploy * (w / sum_w) for sym, w in weights.items()
        }
        allocations: Dict[str, float] = {}
        for sym, raw in raw_allocs.items():
            amt = round(raw, 2)
            if amt >= 1.0:
                allocations[sym] = amt

        deployed = round(sum(allocations.values()), 2)
        reserve = round(cash - deployed, 2)
        rationale = (
            f'Portfolio Advisor: phân bổ ${deployed:.2f}/{cash:.2f} '
            f'({deploy_ratio:.0%} ví) cho {len(allocations)} mã; '
            f'giữ lại ${reserve:.2f}. '
            f'Độ tin cậy TB {avg_conf:.0%}. '
            + ', '.join(risk_notes[:3])
        )
        return {
            'allocations': allocations,
            'deploy_usd': deployed,
            'reserve_usd': reserve,
            'deploy_ratio': round(deploy_ratio, 4),
            'rationale': rationale,
        }


orchestrator = CoinAgentOrchestrator()
