from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///../data/analyst.db"
    ai_provider: str = "mock"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    storage_provider: str = "local"
    storage_path: str = "../data/uploads"
    max_upload_mb: int = 25
    frontend_url: str = "http://localhost:5173"
    analysis_timeout_seconds: int = 10
    ai_request_timeout_seconds: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
