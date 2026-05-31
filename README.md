# Bot Coin — AI Multi-Agent Crypto Analysis

A cryptocurrency analysis platform with **live prices**, on-chain/market details, and an **AI committee debate** — simulating a crypto financial firm's research desk. BUY / HOLD / SELL recommendations are personalized by **how many coins you hold** (including zero).

Built on the [Bot_Trading](../Bot_Trading) architecture (Vietnamese stock analysis), streamlined for 24/7 crypto markets and CoinGecko data.

---

## Table of contents

- [Quick start](#quick-start)
- [Features](#features)
- [User flow](#user-flow)
- [AI committee](#ai-committee)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [API](#api)
- [Project structure](#project-structure)
- [Local development (no Docker)](#local-development-no-docker)
- [Environment variables](#environment-variables)
- [Troubleshooting](#troubleshooting)
- [Legal disclaimer](#legal-disclaimer)

---

## Quick start

```powershell
git clone <repo-url> Bot_Coin
cd Bot_Coin
docker compose up --build
```

**First build** may take **3–10 minutes** (`npm install` inside the frontend container).

### When is it ready?

Wait for logs like:

- `backend` → `Application startup complete`
- `frontend` → `Ready` or `compiled successfully`

### Access

| Service | URL | Description |
|---------|-----|-------------|
| **Dashboard** | http://localhost:3001 | Main UI (Docker) |
| **API** | http://localhost:5566/api/v1 | REST API |
| **Swagger** | http://localhost:5566/docs | Interactive API docs |
| **Health** | http://localhost:5566/ | Backend health check |
| **WebSocket** | `ws://localhost:5566/ws/market` | Live price push |

### Quick check

```powershell
curl http://localhost:5566/api/v1/market/overview
```

Should return JSON with `watchlist` (15 coins) and `indices` (BTC, ETH, BNB).

### Stop / restart

```powershell
docker compose down          # Stop, keep local cache
docker compose up -d --build # Run in background
docker compose logs -f backend
```

---

## Features

| Area | Description |
|------|-------------|
| **Live price table** | 15 top-cap coins: BTC, ETH, BNB, SOL, XRP, ADA, DOGE, AVAX, DOT, LINK, MATIC, UNI, ATOM, LTC, TRX |
| **WebSocket `/ws/market`** | Price updates ~every 10s, no page reload |
| **Coin detail** | Price, 24h volume, market cap, ATH/ATL, volume/market-cap ratio |
| **Run AI analysis** | Enter holdings → Submit → triggers committee debate |
| **AI debate** | 6 specialists + Chair; English summary and BUY/HOLD/SELL vote bar |
| **Portfolio-aware** | **PortfolioAdvisor** uses your actual position (0 = should I buy?; >0 = add / hold / sell) |

**Data source:** [CoinGecko](https://www.coingecko.com/) (free tier). In-memory cache + demo fallback on rate limit.

**Price unit on UI:** USD (`$97,000.00`).

**Market hours:** Crypto trades **24/7**.

---

## User flow

```
Dashboard (live prices)
    │
    ├── Click [Detail] on a coin
    │       └── Modal: price, volume, market cap, ATH/ATL…
    │
    └── Click [Run AI analysis]
            ├── Enter your coin holdings (can be 0)
            ├── Click [Submit]
            └── AI committee debate → Verdict + suggested action
```

**Context examples:**

| Holdings | Committee question |
|----------|------------------|
| `0` | “Should I open a new position?” |
| `0.5 BTC` | “Hold, add more, or take profit?” |
| `100 SOL` | Recommendation tied to position value (~USD) |

---

## AI committee

Simulates a **crypto research desk** — each agent has a perspective; the Chair synthesizes consensus.

| Agent | Role | Main inputs |
|-------|------|-------------|
| **MarketScanner** | 60-day trend & liquidity | OHLC, momentum |
| **OnChainAnalyst** | Market cap, rank, blue-chip vs mid-cap | Market cap, rank |
| **TechnicalAnalyst** | RSI, MACD, SMA | Technical indicators |
| **SentimentAnalysis** | Sentiment & 24h move | % change, price position |
| **RiskManagement** | Volatility, stop-loss, take-profit | ATR, support/resistance |
| **PortfolioAdvisor** | **Recommendation for your holdings** | `holdings`, current price |
| **DecisionMaker** | Chair — final consensus | Votes + agent weights |

Backend pipeline: `coin_agent_orchestrator.py` → `coin_user_brief.py` (English summary).

---

## Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│    Browser      │  HTTP   │     FastAPI      │  HTTP   │   CoinGecko     │
│  Next.js :3001  │────────▶│   Backend :5566  │────────▶│   (prices)      │
└────────┬────────┘         └────────┬─────────┘         └─────────────────┘
         │                           │
         │    ws://…/ws/market       │  In-memory cache (~10s)
         └───────────────────────────┘  Demo fallback on 429
```

| Layer | Stack |
|-------|--------|
| **Frontend** | Next.js 14, TypeScript, Tailwind CSS, TanStack Query |
| **Backend** | FastAPI, Pydantic, httpx, NumPy |
| **Realtime** | WebSocket broadcast after each price sync |
| **AI** | Rule-based multi-agent (no LLM/Ollama required) |

Unlike Bot_Trading: **no PostgreSQL/Redis** — lightweight stack for fast demos.

---

## Requirements

| Software | Required? | Notes |
|----------|-----------|-------|
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | **Recommended** | Compose v2, WSL2 on Windows |
| Git | Yes | Clone repository |
| RAM ≥ 4 GB | Recommended | Next dev + FastAPI |
| Node.js / Python | No* | *If running 100% via Docker |

---

## API

### Main endpoints

```http
GET  /api/v1/market/overview
GET  /api/v1/market/coin/{symbol}
POST /api/v1/agents/debate/{symbol}
GET  /api/v1/agents/debate/{symbol}?holdings=0
WS   ws://localhost:5566/ws/market
```

### Debate with holdings

```http
POST /api/v1/agents/debate/BTC
Content-Type: application/json

{
  "holdings": 0.25
}
```

**Sample response:**

```json
{
  "symbol": "BTC",
  "user_holdings": 0.25,
  "user_brief": {
    "headline": "BTC (holding 0.25) — Consider BUY",
    "verdict_label": "Consider BUY",
    "action": "You may hold and add a small amount if you accept crypto volatility risk.",
    "votes": { "buy": 3, "hold": 2, "sell": 1 }
  },
  "consensus": {
    "verdict": "buy",
    "confidence": 68.5
  }
}
```

### Typical response times

| Endpoint | Time |
|----------|------|
| `market/overview` | < 2s (cached) |
| `market/coin/BTC` | 1–3s |
| `agents/debate/{symbol}` | 2–5s (cached 5 min per symbol + holdings) |
| WebSocket push | ~every 10s |

Full docs: http://localhost:5566/docs

---

## Project structure

```
Bot_Coin/
├── docker-compose.yml
├── README.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── api/v1/routes.py
│       ├── core/config.py
│       └── services/
│           ├── crypto_data.py
│           ├── crypto_technical.py
│           ├── coin_agent_orchestrator.py
│           ├── coin_user_brief.py
│           └── market_ws.py
└── frontend/
    ├── Dockerfile
    ├── app/
    ├── components/
    ├── hooks/
    └── lib/api.ts
```

---

## Local development (no Docker)

For developers comfortable with Python/Node.

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 5566
```

### Frontend

```powershell
cd frontend
npm install
$env:INTERNAL_API_URL="http://127.0.0.1:5566/api/v1"
npm run dev
```

Open **http://localhost:3000** (native Next.js port).

Docker UI: **http://localhost:3001** (`3001:3000` avoids conflict with other apps on port 3000).

The frontend proxies API calls via `/api/v1` on the same origin (except WebSocket).

---

## Environment variables

| Variable | Docker value | Purpose |
|----------|--------------|---------|
| `INTERNAL_API_URL` | `http://backend:8000/api/v1` | Next.js rewrites → backend |
| `NEXT_PUBLIC_WS_PORT` | `5566` | WebSocket port in browser |

Backend (`app/core/config.py`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `COINGECKO_BASE` | `https://api.coingecko.com/api/v3` | API base URL |
| `SYNC_TTL_SECONDS` | `10` | Price sync interval |
| `DEBATE_CACHE_SECONDS` | `300` | Debate result cache TTL |

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `port 5566 already in use` | Old backend still running | Kill process on 5566 or change port in `docker-compose.yml` |
| Watchlist prices = 0 | CoinGecko rate limit / network | Wait 1–2 min; backend falls back to demo; restart backend |
| AI debate fails / timeout | CoinGecko rate limit | Retry after 60s; results cached 5 minutes |
| Blank UI / no CSS | Broken `node_modules` on host | Use Docker volume; `docker compose up --build` |
| `Bind for 0.0.0.0:3000 failed` | Port 3000 taken (Bot_Trading, etc.) | Bot Coin uses **3001** — open http://localhost:3001 |
| 404 on homepage | Wrong URL (`:5566` is API only, or `:3000` with Docker) | Open **http://localhost:3001** |
| API not loading | Proxy not ready | Restart frontend; API goes through `/api/v1` |

### Change ports

```yaml
# docker-compose.yml
ports:
  - '3001:3000'   # frontend
  - '5577:8000'   # backend if 5566 is taken
```

Update `NEXT_PUBLIC_WS_PORT=5577` if you change the backend port.

---

## Legal disclaimer

Bot Coin is a **research and learning tool** that simulates professional analysis workflows. It is **not** investment advice, licensed trading signals, or financial advisory services.

- Crypto is highly volatile — you can lose your entire investment.
- Third-party API data may be delayed or inaccurate.
- Always do your own research and manage risk before trading.

---

## Related projects

| Repo | Description |
|------|-------------|
| [Bot_Trading](../Bot_Trading) | Vietnamese stock analysis — VCI/vnstock, PostgreSQL, AI ranking |
