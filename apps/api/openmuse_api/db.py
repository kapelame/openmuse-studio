from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import settings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_path() -> Path:
    value = settings.database_url
    if value.startswith("sqlite:///"):
        return Path(value.removeprefix("sqlite:///"))
    return Path("./openmuse.db")


class Database:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.init()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                  id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT DEFAULT '',
                  creation_mode TEXT NOT NULL, rights_confirmed INTEGER NOT NULL DEFAULT 0,
                  status TEXT NOT NULL, current_version_id TEXT,
                  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS assets (
                  id TEXT PRIMARY KEY, project_id TEXT NOT NULL, type TEXT NOT NULL,
                  role TEXT NOT NULL, storage_key TEXT NOT NULL, original_filename TEXT NOT NULL,
                  mime_type TEXT NOT NULL, size INTEGER NOT NULL, duration REAL,
                  width INTEGER, height INTEGER, checksum TEXT NOT NULL, metadata TEXT DEFAULT '{}',
                  created_at TEXT NOT NULL, FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS lyrics (
                  id TEXT PRIMARY KEY, project_id TEXT NOT NULL, title TEXT NOT NULL,
                  language TEXT DEFAULT 'und', canonical_text TEXT NOT NULL,
                  structured_lyrics TEXT DEFAULT '[]', source TEXT NOT NULL, created_at TEXT NOT NULL,
                  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS versions (
                  id TEXT PRIMARY KEY, project_id TEXT NOT NULL, parent_version_id TEXT,
                  provider TEXT NOT NULL, provider_model TEXT DEFAULT '', prompt TEXT DEFAULT '',
                  lyrics_id TEXT, audio_asset_id TEXT, generation_parameters TEXT DEFAULT '{}',
                  analysis TEXT DEFAULT '{}', created_at TEXT NOT NULL,
                  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS jobs (
                  id TEXT PRIMARY KEY, project_id TEXT NOT NULL, kind TEXT NOT NULL,
                  provider TEXT DEFAULT '', status TEXT NOT NULL, progress INTEGER DEFAULT 0,
                  attempts INTEGER DEFAULT 0, logs TEXT DEFAULT '[]', error_code TEXT,
                  error_message TEXT, created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT,
                  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS renders (
                  id TEXT PRIMARY KEY, project_id TEXT NOT NULL, template TEXT NOT NULL,
                  aspect_ratio TEXT NOT NULL, resolution TEXT NOT NULL, fps INTEGER NOT NULL,
                  status TEXT NOT NULL, progress INTEGER DEFAULT 0, output_asset_id TEXT,
                  config TEXT DEFAULT '{}', error TEXT, created_at TEXT NOT NULL,
                  completed_at TEXT, FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS release_packs (
                  id TEXT PRIMARY KEY, project_id TEXT NOT NULL, title TEXT NOT NULL,
                  x_hook TEXT DEFAULT '', x_copy TEXT DEFAULT '', description TEXT DEFAULT '',
                  hashtags TEXT DEFAULT '[]', asset_manifest TEXT DEFAULT '{}', created_at TEXT NOT NULL,
                  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
                );
                """
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(projects)").fetchall()}
            if "rights_confirmed" not in columns:
                conn.execute("ALTER TABLE projects ADD COLUMN rights_confirmed INTEGER NOT NULL DEFAULT 0")

    def _one(self, query: str, args: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self._lock, self.connect() as conn:
            row = conn.execute(query, args).fetchone()
            return dict(row) if row else None

    def _all(self, query: str, args: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._lock, self.connect() as conn:
            return [dict(row) for row in conn.execute(query, args).fetchall()]

    def insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        keys = list(values)
        placeholders = ",".join("?" for _ in keys)
        args = tuple(json.dumps(values[k]) if isinstance(values[k], (dict, list)) else values[k] for k in keys)
        with self._lock, self.connect() as conn:
            conn.execute(f"INSERT INTO {table} ({','.join(keys)}) VALUES ({placeholders})", args)
            row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (values["id"],)).fetchone()
            return dict(row)

    def update(self, table: str, row_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
        keys = list(values)
        args = tuple(json.dumps(values[k]) if isinstance(values[k], (dict, list)) else values[k] for k in keys)
        with self._lock, self.connect() as conn:
            conn.execute(f"UPDATE {table} SET {','.join(f'{k}=?' for k in keys)} WHERE id=?", (*args, row_id))
        return self._one(f"SELECT * FROM {table} WHERE id = ?", (row_id,))

    def project(self, project_id: str) -> dict[str, Any] | None:
        project = self._one("SELECT * FROM projects WHERE id=?", (project_id,))
        if not project:
            return None
        project["assets"] = self._all("SELECT * FROM assets WHERE project_id=? ORDER BY created_at", (project_id,))
        project["lyrics"] = self._all("SELECT * FROM lyrics WHERE project_id=? ORDER BY created_at DESC", (project_id,))
        project["versions"] = self._all("SELECT * FROM versions WHERE project_id=? ORDER BY created_at DESC", (project_id,))
        project["jobs"] = self._all("SELECT * FROM jobs WHERE project_id=? ORDER BY created_at DESC", (project_id,))
        project["renders"] = self._all("SELECT * FROM renders WHERE project_id=? ORDER BY created_at DESC", (project_id,))
        return project

    def list_projects(self) -> list[dict[str, Any]]:
        return self._all("SELECT * FROM projects ORDER BY updated_at DESC")

    def make_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:12]}"


db = Database()
