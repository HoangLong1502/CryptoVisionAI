from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    coingecko_base: str = 'https://api.coingecko.com/api/v3'
    binance_api_base: str = 'https://api.binance.com'
    binance_ws_base: str = 'wss://stream.binance.com:9443'
    binance_api_key: str = ''
    binance_api_secret: str = ''
    sync_ttl_seconds: int = 60
    live_broadcast_ms: int = 200
    metadata_refresh_seconds: int = 30
    debate_cache_seconds: int = 300
    paper_trading_initial_balance: float = 1000
    paper_wallet_path: str = 'data/paper_wallet.json'
    custom_watchlist_path: str = 'data/custom_watchlist.json'
    screener_refresh_seconds: int = 600
    screener_cache_seconds: int = 600
    auto_trading_state_path: str = 'data/auto_trading.json'
    auto_trade_interval_ms: int = 200
    auto_trade_cooldown_seconds: int = 300
    auto_trade_min_profit_usd: float = 0.25
    auto_trade_min_buy_score: float = 70.0
    auto_trade_kill_consecutive_losses: int = 5
    auto_trade_kill_daily_loss_pct: float = 3.0
    # Risk limits — tránh cháy tài khoản
    auto_trade_max_deploy_pct: float = 0.80
    auto_trade_max_position_pct: float = 0.20
    auto_trade_stop_loss_pct: float = 5.0
    auto_trade_stop_loss_usd: float = 0.0
    auto_trade_max_drawdown_pct: float = 10.0
    performance_history_path: str = 'data/performance_history.json'
    performance_snapshot_min_seconds: int = 3600

    class Config:
        env_file = '.env'


settings = Settings()
