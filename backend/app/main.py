import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.routes import router as api_router
from app.services.binance_realtime import start_binance_realtime
from app.services.market_ws import register as ws_register, unregister as ws_unregister

app = FastAPI(title='Bot Coin AI Platform')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(api_router, prefix='/api/v1')


@app.on_event('startup')
async def startup_event():
    asyncio.create_task(start_binance_realtime())


@app.get('/')
async def root():
    return JSONResponse({'service': 'Bot Coin AI backend', 'status': 'running'})


@app.websocket('/ws/market')
async def websocket_endpoint(websocket: WebSocket):
    await ws_register(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == 'ping':
                await websocket.send_json({'type': 'pong'})
    except WebSocketDisconnect:
        await ws_unregister(websocket)
    except Exception:
        await ws_unregister(websocket)
