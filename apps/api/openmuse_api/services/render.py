from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from ..config import settings
from ..db import db, utc_now
from ..services.media import asset_url
from packages.timeline.subtitles import Cue, generate_ass, parse_subtitles

ASPECTS = {
    "1:1": (1080, 1080),
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "4:5": (1080, 1350),
}


class RenderError(RuntimeError):
    pass


def run_ffmpeg(args: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["ffmpeg", "-hide_banner", "-y", *args], capture_output=True, text=True, check=False)
    if result.returncode:
        raise RenderError(f"FFmpeg failed ({result.returncode}): {result.stderr[-1200:].strip()}")
    return result


def has_filter(name: str) -> bool:
    result = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True, check=False)
    return any(line.split() and line.split()[-1] == name for line in result.stdout.splitlines())


def _font_path() -> str | None:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Verdana.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    return next((candidate for candidate in candidates if Path(candidate).exists()), None)


def make_subtitle_overlays(cues: list[Cue], width: int, height: int, output_dir: Path, color: str, alignment: str) -> list[tuple[Path, float, float]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    overlays: list[tuple[Path, float, float]] = []
    font_path = _font_path()
    rgb = tuple(int(color.lstrip("#")[index:index + 2], 16) for index in (0, 2, 4)) if len(color.lstrip("#")) == 6 else (244, 240, 232)
    font = ImageFont.truetype(font_path, 52) if font_path else ImageFont.load_default(size=52)
    for index, cue in enumerate(cues):
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        lines = cue.text.splitlines()[:2]
        rendered = "\n".join(lines)
        box = draw.multiline_textbbox((0, 0), rendered, font=font, spacing=8, align="left")
        text_width = box[2] - box[0]
        x = round(width * 0.09) if alignment == "left" else round((width - text_width) / 2)
        y = round(height * 0.82 - (box[3] - box[1]))
        # A low-alpha panel keeps light text readable without KTV-style outlines or glow.
        pad_x, pad_y = 16, 12
        draw.rounded_rectangle((x - pad_x, y - pad_y, x + text_width + pad_x, y + (box[3] - box[1]) + pad_y), radius=10, fill=(16, 16, 15, 42))
        draw.multiline_text((x, y), rendered, font=font, fill=(*rgb, 245), spacing=8, align="left")
        path = output_dir / f"subtitle-{index:03d}.png"
        image.save(path)
        overlays.append((path, cue.start_ms / 1000, cue.end_ms / 1000))
    return overlays


def probe(path: Path) -> dict[str, Any]:
    result = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)], capture_output=True, text=True, check=False)
    if result.returncode:
        raise RenderError(result.stderr[-800:].strip())
    return json.loads(result.stdout or "{}")


def render_video(project_id: str, render_id: str, audio_path: Path, cover_path: Path, subtitle_path: Path | None, config: dict[str, Any], output_path: Path) -> dict[str, Any]:
    width, height = ASPECTS.get(config.get("aspect_ratio", "1:1"), ASPECTS["1:1"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    audio_probe = probe(audio_path)
    audio_duration = float(audio_probe.get("format", {}).get("duration") or 0)
    duration_args = ["-t", f"{audio_duration:.3f}"] if audio_duration else []
    ass_path = output_path.with_suffix(".ass")
    cues: list[Cue] = parse_subtitles(subtitle_path) if subtitle_path and subtitle_path.exists() else []
    ass_path.write_text(generate_ass(cues, width, height, config.get("subtitle_color", "#F4F0E8"), config.get("subtitle_alignment", "left"), config.get("title")), encoding="utf-8")
    # Scale and crop with a single deterministic frame expression. No random motion and no rotation.
    vf = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},format=yuv420p"
    if cues and has_filter("subtitles"):
        subtitle_filter_path = str(ass_path).replace("\\", "/").replace("'", "\\'")
        vf += f",subtitles=filename='{subtitle_filter_path}'"
        run_ffmpeg(["-loop", "1", "-i", str(cover_path), "-i", str(audio_path), "-vf", vf, "-r", str(config.get("fps", 24)), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-shortest", *duration_args, "-movflags", "+faststart", str(output_path)])
    elif cues:
        overlays = make_subtitle_overlays(cues, width, height, output_path.parent / f"{output_path.stem}-subtitle-overlays", config.get("subtitle_color", "#F4F0E8"), config.get("subtitle_alignment", "left"))
        inputs = ["-loop", "1", "-i", str(cover_path), "-i", str(audio_path)]
        for path, _, _ in overlays:
            inputs += ["-loop", "1", "-i", str(path)]
        chain = [f"[0:v]{vf}[base]"]
        current = "base"
        for index, (_, start, end) in enumerate(overlays):
            next_name = f"v{index}"
            chain.append(f"[{current}][{index + 2}:v]overlay=0:0:enable='between(t,{start:.3f},{end:.3f})'[{next_name}]")
            current = next_name
        run_ffmpeg([*inputs, "-filter_complex", ";".join(chain), "-map", f"[{current}]", "-map", "1:a", "-r", str(config.get("fps", 24)), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-shortest", *duration_args, "-movflags", "+faststart", str(output_path)])
    else:
        run_ffmpeg(["-loop", "1", "-i", str(cover_path), "-i", str(audio_path), "-vf", vf, "-r", str(config.get("fps", 24)), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-shortest", *duration_args, "-movflags", "+faststart", str(output_path)])
    result = probe(output_path)
    streams = result.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), {})
    duration = float(result.get("format", {}).get("duration") or 0)
    return {"duration": duration, "width": video.get("width"), "height": video.get("height"), "fps": video.get("r_frame_rate"), "video_codec": video.get("codec_name"), "pixel_format": video.get("pix_fmt"), "audio_codec": audio.get("codec_name"), "sample_rate": audio.get("sample_rate"), "channels": audio.get("channels"), "has_video": bool(video), "has_audio": bool(audio), "ass_path": str(ass_path)}


def make_contact_sheet(video_path: Path, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(["-i", str(video_path), "-vf", "fps=1/5,scale=320:-1,tile=3x2", "-frames:v", "1", str(output_path)])
    return output_path
