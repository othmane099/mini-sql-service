from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "mini-sql-service"
    DEBUG: str = "TRUE"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = "*"

    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 5
    DATABASE_POOL_TTL: int = 60 * 20
    DATABASE_POOL_PRE_PING: bool = True

    ADMIN_API_KEY: str = "change-me-in-production"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origins_list(self) -> list[str]:
        raw = self.CORS_ORIGINS.strip()
        if not raw:
            return []
        return [p.strip() for p in raw.split(",") if p.strip()]

    @property
    def is_debug(self) -> bool:
        return self.DEBUG.lower() == "true"


settings = Settings()
