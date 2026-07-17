from __future__ import annotations

import json
import os
import stat

from fastapi.testclient import TestClient

from openmuse_api import config
from openmuse_api.config import settings
from openmuse_api.main import app


def test_runtime_settings_are_persisted_with_restricted_permissions(tmp_path, monkeypatch) -> None:
    path = tmp_path / "settings.json"
    monkeypatch.setattr(config, "RUNTIME_SETTINGS_PATH", path)
    for key in config.RUNTIME_SETTING_KEYS:
        monkeypatch.setattr(settings, key, getattr(settings, key))

    config.save_runtime_settings({"default_music_provider": "minimax", "minimax_api_key": "test-secret"})
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["minimax_api_key"] == "test-secret"
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    public = config.public_runtime_settings()
    assert public["minimax_api_key_configured"] is True
    assert "test-secret" not in json.dumps(public)


def test_settings_api_writes_key_without_returning_it(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "RUNTIME_SETTINGS_PATH", tmp_path / "settings.json")
    for key in config.RUNTIME_SETTING_KEYS:
        monkeypatch.setattr(settings, key, getattr(settings, key))

    client = TestClient(app)
    response = client.put(
        "/api/settings",
        json={"default_music_provider": "mock", "minimax_api_key": "test-secret", "minimax_music_model": "music-fixture"},
    )
    assert response.status_code == 200
    assert response.json()["settings"]["minimax_api_key_configured"] is True
    assert "test-secret" not in response.text
    assert json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))["minimax_music_model"] == "music-fixture"

    cleared = client.put("/api/settings", json={"clear_minimax_api_key": True})
    assert cleared.status_code == 200
    assert cleared.json()["settings"]["minimax_api_key_configured"] is False
