from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    coingecko_base: str = 'https://api.coingecko.com/api/v3'
    binance_api_base: str = 'https://api.binance.com'
    binance_ws_base: str = 'wss://stream.binance.com:9443'
    sync_ttl_seconds: int = 60
    live_broadcast_ms: int = 200
    metadata_refresh_seconds: int = 30
    debate_cache_seconds: int = 300
    paper_trading_initial_balance: float = 10_000.0
    paper_wallet_path: str = 'data/paper_wallet.json'
    custom_watchlist_path: str = 'data/custom_watchlist.json'
    screener_refresh_seconds: int = 600
    screener_cache_seconds: int = 600
    auto_trading_state_path: str = 'data/auto_trading.json'
    auto_trade_interval_ms: int = 200
    auto_trade_buy_usd: float = 100.0
    auto_trade_max_positions: int = 5
    auto_trade_max_cash_pct: float = 0.15
    auto_trade_cooldown_seconds: int = 300
    performance_history_path: str = 'data/performance_history.json'
    performance_snapshot_min_seconds: int = 3600

    class Config:
        env_file = '.env'


settings = Settings()
