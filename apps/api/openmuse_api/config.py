from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "OpenMuse Studio"
    app_env: str = "development"
    database_url: str = "sqlite:///./openmuse.db"
    redis_url: str = "redis://localhost:6379/0"
    redis_queue_name: str = "openmuse:jobs"
    storage_root: Path = Path("./storage")
    minimax_api_key: str = ""
    minimax_api_base: str = "https://api.minimaxi.com"
    minimax_music_model: str = "music-2.6"
    minimax_cover_model: str = "music-cover"
    default_music_provider: str = "mock"
    default_image_provider: str = "mock"
    custom_music_endpoint: str = ""
    custom_image_endpoint: str = ""
    enable_local_asr: bool = False
    enable_demucs: bool = False
    enable_basic_pitch: bool = False
    max_upload_bytes: int = 100 * 1024 * 1024
    max_audio_seconds: int = 900

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)


settings = Settings()
settings.storage_root.mkdir(parents=True, exist_ok=True)
