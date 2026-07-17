from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image

from ..db import db, utc_now
from packages.timeline.subtitles import cues_to_lrc, cues_to_srt, generate_ass, parse_subtitles


def build_release_pack(project: dict[str, Any], project_root: Path, output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    title = project["title"]
    x_hook = f"{title} — an original AI-assisted track from OpenMuse Studio"
    x_copy = f"New track: {title}, made in OpenMuse Studio.\n\nStarted with a focused musical idea and turned it into a finished song with synchronized lyrics and a lyric video.\n\n#AIMusic"
    description = project.get("description") or "An original track created and packaged with OpenMuse Studio."
    asset_manifest: dict[str, str] = {}
    for asset in project.get("assets", []):
        source = Path(asset["storage_key"])
        if not source.exists():
            continue
        target = output_root / source.name
        shutil.copy2(source, target)
        asset_manifest[asset["type"] + ":" + asset["role"]] = target.name
    audio = next((asset for asset in project.get("assets", []) if asset["type"] == "audio"), None)
    if audio and Path(audio["storage_key"]).exists():
        source = Path(audio["storage_key"])
        subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", str(source), "-c:a", "pcm_s16le", str(output_root / "song.wav")], capture_output=True, check=True)
        subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", str(source), "-c:a", "libmp3lame", "-b:a", "256k", str(output_root / "song.mp3")], capture_output=True, check=True)
        asset_manifest["song_wav"] = "song.wav"
        asset_manifest["song_mp3"] = "song.mp3"
    cover = next((asset for asset in project.get("assets", []) if asset["type"] == "image"), None)
    if cover and Path(cover["storage_key"]).exists():
        with Image.open(cover["storage_key"]).convert("RGB") as source:
            side = min(source.width, source.height)
            left, top = (source.width - side) // 2, (source.height - side) // 2
            square = source.crop((left, top, left + side, top + side))
            square.resize((3000, 3000), Image.Resampling.LANCZOS).save(output_root / "cover-3000.png", "PNG")
            square.resize((1080, 1080), Image.Resampling.LANCZOS).save(output_root / "cover-1080.jpg", "JPEG", quality=92)
            asset_manifest["cover_3000"] = "cover-3000.png"
            asset_manifest["cover_1080"] = "cover-1080.jpg"
    subtitle = next((asset for asset in project.get("assets", []) if asset["type"] == "subtitle"), None)
    if subtitle and Path(subtitle["storage_key"]).exists():
        cues = parse_subtitles(Path(subtitle["storage_key"]))
        (output_root / "lyrics.txt").write_text("\n".join(cue.text for cue in cues) + "\n", encoding="utf-8")
        (output_root / "lyrics.lrc").write_text(cues_to_lrc(cues), encoding="utf-8")
        (output_root / "lyrics.srt").write_text(cues_to_srt(cues), encoding="utf-8")
        (output_root / "lyrics.ass").write_text(generate_ass(cues, 1080, 1080), encoding="utf-8")
        asset_manifest.update({"lyrics_txt": "lyrics.txt", "lyrics_lrc": "lyrics.lrc", "lyrics_srt": "lyrics.srt", "lyrics_ass": "lyrics.ass"})
    video = next((asset for asset in project.get("assets", []) if asset["type"] == "video"), None)
    if video and Path(video["storage_key"]).exists():
        shutil.copy2(video["storage_key"], output_root / "mv-square.mp4")
        asset_manifest["mv_square"] = "mv-square.mp4"
    (output_root / "title.txt").write_text(x_hook + "\n", encoding="utf-8")
    (output_root / "x-copy.txt").write_text(x_copy + "\n", encoding="utf-8")
    (output_root / "description.txt").write_text(description + "\n", encoding="utf-8")
    metadata = {"project_id": project["id"], "title": title, "provider": "openmuse", "assets": asset_manifest, "generated_at": utc_now()}
    (output_root / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest = {"project": project, "assets": asset_manifest, "api_keys_included": False}
    (output_root / "project.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    return {"output_root": str(output_root), "files": sorted(path.name for path in output_root.iterdir())}
