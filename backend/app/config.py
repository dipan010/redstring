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
    # cheaper models for steps that only write text (they do not affect the risk score)
    verdict_model: str = "gemini-2.5-flash-lite"
    chat_model: str = "gemini-2.5-flash"
    draft_model: str = "gemini-2.5-flash-lite"
    storage_bucket: str = "redstring-511910.firebasestorage.app"
    auth_disabled: bool = False

    # Cloud Tasks dispatch (empty queue = run in-process, for local dev)
    tasks_queue: str = ""
    service_url: str = "https://redstring-api-283581061982.us-central1.run.app"
    tasks_invoker_sa: str = "283581061982-compute@developer.gserviceaccount.com"

    # abuse limits for the public prototype
    claims_per_user_per_hour: int = 15
    chat_per_user_per_hour: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
