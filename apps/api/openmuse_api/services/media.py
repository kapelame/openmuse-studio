from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import secrets
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image

from ..config import settings

AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
SUBTITLE_EXTS = {".txt", ".lrc", ".srt", ".ass", ".vtt"}
MIDI_EXTS = {".mid", ".midi"}


class MediaError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _ffprobe(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise MediaError(f"ffprobe rejected media: {result.stderr[-500:].strip()}")
    return json.loads(result.stdout or "{}")


def validate_media(path: Path, filename: str, content_type: str | None = None) -> dict[str, Any]:
    suffix = Path(filename).suffix.lower()
    size = path.stat().st_size
    if size > settings.max_upload_bytes:
        raise MediaError(f"File exceeds {settings.max_upload_bytes} byte limit")
    if suffix in IMAGE_EXTS:
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                return {"kind": "image", "width": image.width, "height": image.height, "format": image.format}
        except Exception as exc:
            raise MediaError(f"Invalid image: {exc}") from exc
    if suffix in AUDIO_EXTS:
        probe = _ffprobe(path)
        streams = probe.get("streams", [])
        audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
        if not audio:
            raise MediaError("No audio stream found")
        duration = float(probe.get("format", {}).get("duration") or audio.get("duration") or 0)
        if duration > settings.max_audio_seconds:
            raise MediaError(f"Audio exceeds {settings.max_audio_seconds} second limit")
        return {
            "kind": "audio", "duration": duration, "channels": audio.get("channels"),
            "sample_rate": audio.get("sample_rate"), "codec": audio.get("codec_name"),
            "bit_rate": audio.get("bit_rate"), "format": probe.get("format", {}).get("format_name"),
        }
    if suffix in SUBTITLE_EXTS:
        if path.stat().st_size > 5 * 1024 * 1024:
            raise MediaError("Subtitle file is too large")
        path.read_text(encoding="utf-8-sig")
        return {"kind": "subtitle", "format": suffix.removeprefix(".")}
    if suffix in MIDI_EXTS:
        if path.read_bytes()[:4] != b"MThd":
            raise MediaError("Invalid MIDI header")
        return {"kind": "midi", "format": "midi"}
    raise MediaError(f"Unsupported media type: {suffix or content_type or 'unknown'}")


def safe_storage_path(project_id: str, filename: str) -> Path:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).name) or "asset"
    root = settings.storage_root / project_id
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{secrets.token_hex(10)}-{clean}"


def asset_url(project_id: str, asset_id: str) -> str:
    return f"/api/projects/{project_id}/assets/{asset_id}/download"
