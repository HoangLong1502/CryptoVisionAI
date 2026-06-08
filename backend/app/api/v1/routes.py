from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.coin_agent_orchestrator import orchestrator
from app.services.coin_user_brief import build_coin_user_brief
from app.services.crypto_data import DEFAULT_WATCHLIST, get_coin_detail, get_historical_prices, sync_market_snapshot
from app.services.crypto_technical import full_historical_analysis

router = APIRouter()

_debate_cache: Dict[str, Any] = {}


class DebateRequest(BaseModel):
    holdings: float = Field(default=0.0, ge=0, description='Amount of coin the user holds (may be 0)')


def _debate_cache_key(symbol: str, holdings: float) -> str:
    return f'{symbol.upper()}:{holdings:.8f}'


@router.get('/market/overview')
async def market_overview():
    try:
        body = await sync_market_snapshot()
        return JSONResponse(body)
    except Exception as e:
        return JSONResponse(
            {
                'indices': [],
                'watchlist': [{'symbol': s, 'price': 0, 'change': 0} for s in DEFAULT_WATCHLIST],
                'top_gainers': [],
                'top_losers': [],
                'error': str(e),
            },
            status_code=200,
        )


@router.get('/market/coin/{symbol}')
async def coin_detail(symbol: str):
    sym = symbol.strip().upper()
    detail = await get_coin_detail(sym)
    if not detail:
        return JSONResponse({'error': f'No data for {sym}'}, status_code=404)
    return JSONResponse(detail)


@router.post('/agents/debate/{symbol}')
async def post_debate(symbol: str, body: DebateRequest):
    """AI debate with user holdings context."""
    return await _run_debate(symbol, body.holdings)


@router.get('/agents/debate/{symbol}')
async def get_debate(symbol: str, holdings: float = Query(0.0, ge=0)):
    """GET compatibility — defaults holdings=0."""
    return await _run_debate(symbol, holdings)


async def _run_debate(symbol: str, holdings: float) -> JSONResponse:
    sym = symbol.strip().upper()
    key = _debate_cache_key(sym, holdings)
    now = time.monotonic()
    cached = _debate_cache.get(key)
    if cached and now - cached['ts'] < settings.debate_cache_seconds:
        return JSONResponse(cached['body'])

    try:
        agent_results = await orchestrator.run_coin_pipeline(sym, user_holdings=holdings)
        prices = agent_results.get('historical_prices') or await get_historical_prices(sym, days=60)
        hist = agent_results.get('historical_analysis') or await full_historical_analysis(sym, prices)
        detail = agent_results.get('coin_detail') or await get_coin_detail(sym)

        debate = [
            {
                'agent': ag['agent'],
                'verdict': ag['verdict'],
                'confidence': round(float(ag['score']) * 100, 1),
                'rationale': ag['rationale'],
                'details': ag.get('extra', {}),
            }
            for ag in agent_results.get('agents', [])
            if ag.get('agent') != 'DecisionMaker'
        ]

        decision = agent_results.get('decision', {})
        extra = decision.get('extra', {}) or {}
        user_brief = build_coin_user_brief(
            sym, agent_results, coin_detail=detail, historical_analysis=hist, prices=prices,
            indicators=agent_results.get('indicators'),
        )

        body = {
            'symbol': sym,
            'user_holdings': holdings,
            'user_brief': user_brief,
            'debate': debate,
            'workflow': agent_results.get('workflow'),
            'consensus': {
                'verdict': decision.get('verdict', 'hold'),
                'confidence': round(float(decision.get('score', 0)) * 100, 1),
                'reasoning': decision.get('rationale', ''),
                'consensus_strength': round(float(extra.get('consensus_strength', 0)) * 100, 1),
                'agent_votes': {
                    'buy': int(extra.get('buy_agents', 0)),
                    'hold': int(extra.get('hold_agents', 0)),
                    'sell': int(extra.get('sell_agents', 0)),
                },
            },
            'current_price': (detail or {}).get('prices', {}).get('last'),
            'timestamp': agent_results.get('timestamp'),
        }
        _debate_cache[key] = {'ts': now, 'body': body}
        return JSONResponse(body)
    except Exception as e:
        return JSONResponse({'error': str(e), 'symbol': sym}, status_code=500)
