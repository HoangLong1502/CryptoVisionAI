from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    coingecko_base: str = 'https://api.coingecko.com/api/v3'
    binance_api_base: str = 'https://api.binance.com'
    binance_ws_base: str = 'wss://stream.binance.com:9443'
    sync_ttl_seconds: int = 60
    live_broadcast_ms: int = 200
    metadata_refresh_seconds: int = 30
    debate_cache_seconds: int = 300

    class Config:
        env_file = '.env'


settings = Settings()
