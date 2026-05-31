"""WebSocket push for crypto prices."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Set

from fastapi import WebSocket

from app.services.crypto_data import sync_market_snapshot

_connections: Set[WebSocket] = set()
_lock = asyncio.Lock()


async def build_market_push_payload() -> Dict[str, Any]:
    overview = await sync_market_snapshot()
    return {
        'type': 'market_update',
        **overview,
    }


async def register(websocket: WebSocket) -> None:
    await websocket.accept()
    async with _lock:
        _connections.add(websocket)
    try:
        await websocket.send_json(await build_market_push_payload())
    except Exception:
        pass


async def unregister(websocket: WebSocket) -> None:
    async with _lock:
        _connections.discard(websocket)


async def broadcast_market_update() -> None:
    if not _connections:
        return
    payload = await build_market_push_payload()
    async with _lock:
        targets = list(_connections)
    dead: List[WebSocket] = []
    for ws in targets:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    if dead:
        async with _lock:
            for ws in dead:
                _connections.discard(ws)


async def notify_market_update() -> None:
    try:
        await broadcast_market_update()
    except Exception:
        pass
