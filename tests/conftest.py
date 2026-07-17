from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_runtime(tmp_path, monkeypatch):
    """Keep API and media tests out of the developer's local project database."""
    from openmuse_api.config import settings
    from openmuse_api.db import db

    monkeypatch.setattr(db, "path", tmp_path / "openmuse-test.db")
    monkeypatch.setattr(settings, "storage_root", tmp_path / "storage")
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    db.init()
    yield
