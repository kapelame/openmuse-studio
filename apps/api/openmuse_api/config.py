from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


RUNTIME_SETTINGS_PATH = Path(os.getenv("OPENMUSE_SETTINGS_FILE", ".openmuse/settings.json"))
RUNTIME_SETTING_KEYS = {
    "default_music_provider",
    "default_image_provider",
    "minimax_api_key",
    "minimax_api_base",
    "minimax_music_model",
    "minimax_cover_model",
    "custom_music_endpoint",
    "custom_image_endpoint",
    "enable_local_asr",
    "enable_demucs",
    "enable_basic_pitch",
}


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


def _read_runtime_overrides() -> dict[str, Any]:
    try:
        value = json.loads(RUNTIME_SETTINGS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    if not isinstance(value, dict):
        return {}
    return {key: value[key] for key in RUNTIME_SETTING_KEYS if key in value}


def reload_runtime_settings() -> Settings:
    """Apply UI/first-run overrides without putting secrets in the database."""
    for key, value in _read_runtime_overrides().items():
        setattr(settings, key, value)
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    return settings


def save_runtime_settings(updates: dict[str, Any]) -> Settings:
    current = _read_runtime_overrides()
    current.update({key: value for key, value in updates.items() if key in RUNTIME_SETTING_KEYS})
    RUNTIME_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = RUNTIME_SETTINGS_PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(current, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(RUNTIME_SETTINGS_PATH)
    return reload_runtime_settings()


def public_runtime_settings() -> dict[str, Any]:
    return {
        "default_music_provider": settings.default_music_provider,
        "default_image_provider": settings.default_image_provider,
        "minimax_api_base": settings.minimax_api_base,
        "minimax_music_model": settings.minimax_music_model,
        "minimax_cover_model": settings.minimax_cover_model,
        "minimax_api_key_configured": bool(settings.minimax_api_key),
        "custom_music_endpoint": settings.custom_music_endpoint,
        "custom_image_endpoint": settings.custom_image_endpoint,
        "enable_local_asr": settings.enable_local_asr,
        "enable_demucs": settings.enable_demucs,
        "enable_basic_pitch": settings.enable_basic_pitch,
        "settings_file": str(RUNTIME_SETTINGS_PATH),
    }


reload_runtime_settings()
