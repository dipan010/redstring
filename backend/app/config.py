from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    google_cloud_project: str = "redstring-511910"
    google_cloud_location: str = "us-central1"
    gemini_model: str = "gemini-3.5-flash"
    gemini_location: str = "global"  # newer Gemini models are served from the global endpoint
    gemini_fallback_model: str = "gemini-2.5-flash"  # used when the primary is slow or rate-limited
    gemini_timeout_s: float = 25.0
    storage_bucket: str = "redstring-511910.firebasestorage.app"
    auth_disabled: bool = False

    # abuse limits for the public prototype
    claims_per_user_per_hour: int = 15
    chat_per_user_per_hour: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
