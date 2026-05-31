from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    coingecko_base: str = 'https://api.coingecko.com/api/v3'
    sync_ttl_seconds: int = 10
    debate_cache_seconds: int = 300

    class Config:
        env_file = '.env'


settings = Settings()
