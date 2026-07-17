from __future__ import annotations

import asyncio
import json
import mimetypes
import shutil
import subprocess
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .config import settings
from .db import db, utc_now
from .providers import provider_registry
from .schemas import CreateProjectRequest, EditCommandRequest, RenderRequest, UpdateLyricsRequest
from .services.analysis import analyze_audio
from .services.media import MediaError, asset_url, safe_storage_path, sha256_file, validate_media
from .services.planner import mock_edit_plan
from .services.queue import QueueUnavailable, clear_cancelled, enqueue, mark_cancelled
from .services.release import build_release_pack
from .services.render import ASPECTS, make_contact_sheet, render_video
from packages.timeline.subtitles import Cue, cues_to_lrc, cues_to_srt, generate_ass

app = FastAPI(title=settings.app_name, version="0.1.0", description="Open-source AI music workspace API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


def parse_json_fields(row: dict[str, Any]) -> dict[str, Any]:
    decoded = dict(row)
    for key in ("metadata", "structured_lyrics", "generation_parameters", "analysis", "config", "logs", "hashtags", "asset_manifest"):
        if key in decoded and isinstance(decoded[key], str):
            try:
                decoded[key] = json.loads(decoded[key])
            except json.JSONDecodeError:
                pass
    return decoded


def project_response(project: dict[str, Any]) -> dict[str, Any]:
    output = parse_json_fields(project)
    for group in ("assets", "lyrics", "versions", "jobs", "renders"):
        output[group] = [parse_json_fields(item) for item in output.get(group, [])]
        for asset in output[group]:
            if group == "assets":
                asset["url"] = asset_url(project["id"], asset["id"])
    return output


def asset_by_role(project: dict[str, Any], asset_type: str, role: str | None = None) -> dict[str, Any] | None:
    for asset in project.get("assets", []):
        if asset["type"] == asset_type and (role is None or asset["role"] == role):
            return asset
    return None


def placeholder_cover(path: Path, title: str) -> None:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (1080, 1080), "#e8e4dc")
    draw = ImageDraw.Draw(image)
    for x in range(0, 1080, 72):
        draw.line((x, 0, 1080 - x, 1080), fill="#d6d0c6", width=2)
    draw.rectangle((72, 72, 1008, 1008), outline="#22211f", width=3)
    font = ImageFont.load_default(size=52)
    draw.text((110, 850), title[:36], fill="#22211f", font=font)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG")


def create_job(project_id: str, kind: str, provider: str = "local") -> dict[str, Any]:
    return db.insert("jobs", {"id": db.make_id("job"), "project_id": project_id, "kind": kind, "provider": provider, "status": "queued", "progress": 0, "attempts": 0, "logs": [], "created_at": utc_now()})


def log_job(job_id: str, message: str, progress: int | None = None, **extra: Any) -> None:
    job = db._one("SELECT * FROM jobs WHERE id=?", (job_id,))
    if not job:
        return
    logs = json.loads(job.get("logs") or "[]")
    logs.append({"at": utc_now(), "message": message, **extra})
    values: dict[str, Any] = {"logs": logs}
    if progress is not None:
        values["progress"] = progress
    db.update("jobs", job_id, values)


def render_job_sync(project_id: str, render_id: str, job_id: str, request: dict[str, Any]) -> None:
    try:
        job = db._one("SELECT attempts FROM jobs WHERE id=?", (job_id,)) or {"attempts": 0}
        db.update("jobs", job_id, {"status": "running", "started_at": utc_now(), "attempts": int(job.get("attempts") or 0) + 1, "progress": 5})
        db.update("renders", render_id, {"status": "running", "progress": 5})
        project = db.project(project_id)
        if not project:
            raise RuntimeError("Project not found")
        audio = asset_by_role(project, "audio")
        cover = asset_by_role(project, "image", "cover") or asset_by_role(project, "image")
        subtitle = asset_by_role(project, "subtitle")
        if not audio:
            raise RuntimeError("Upload an audio asset before rendering")
        audio_path = Path(audio["storage_key"])
        if not cover:
            cover_path = settings.storage_root / project_id / "generated-placeholder.png"
            placeholder_cover(cover_path, project["title"])
            log_job(job_id, "No cover uploaded; using deterministic placeholder cover", 22)
        else:
            cover_path = Path(cover["storage_key"])
        subtitle_path = Path(subtitle["storage_key"]) if subtitle else None
        output_path = settings.storage_root / project_id / "renders" / f"{render_id}.mp4"
        log_job(job_id, "Validated inputs and prepared deterministic crop", 28)
        result = render_video(project_id, render_id, audio_path, cover_path, subtitle_path, request, output_path)
        log_job(job_id, "Rendered H.264/AAC video with libass subtitles", 78, probe=result)
        contact = make_contact_sheet(output_path, output_path.with_name(f"{render_id}-contact-sheet.jpg"))
        result["contact_sheet"] = str(contact)
        duration = result.get("duration", 0)
        audio_duration = float(audio.get("duration") or 0)
        if audio_duration and abs(duration - audio_duration) > 0.15:
            raise RuntimeError(f"Audio/video duration mismatch: {duration:.3f}s vs {audio_duration:.3f}s")
        current_job = db._one("SELECT status FROM jobs WHERE id=?", (job_id,))
        if current_job and current_job["status"] == "cancelled":
            db.update("renders", render_id, {"status": "cancelled", "error": "Cancelled by user", "completed_at": utc_now()})
            return
        output_asset = db.insert("assets", {"id": db.make_id("asset"), "project_id": project_id, "type": "video", "role": "rendered_mv", "storage_key": str(output_path), "original_filename": output_path.name, "mime_type": "video/mp4", "size": output_path.stat().st_size, "duration": duration, "width": result.get("width"), "height": result.get("height"), "checksum": sha256_file(output_path), "metadata": result, "created_at": utc_now()})
        db.update("renders", render_id, {"status": "succeeded", "progress": 100, "output_asset_id": output_asset["id"], "config": request, "completed_at": utc_now()})
        db.update("jobs", job_id, {"status": "succeeded", "progress": 100, "finished_at": utc_now()})
        db.update("projects", project_id, {"status": "ready", "updated_at": utc_now()})
    except Exception as exc:
        message = str(exc)
        log_job(job_id, message, 100)
        db.update("jobs", job_id, {"status": "failed", "error_message": message, "error_code": "RENDER_FAILED", "finished_at": utc_now()})
        db.update("renders", render_id, {"status": "failed", "error": message, "completed_at": utc_now()})


def analyze_audio_job_sync(project_id: str, asset_id: str, job_id: str) -> None:
    try:
        job = db._one("SELECT attempts FROM jobs WHERE id=?", (job_id,)) or {"attempts": 0}
        db.update("jobs", job_id, {"status": "running", "started_at": utc_now(), "attempts": int(job.get("attempts") or 0) + 1, "progress": 15})
        asset = db._one("SELECT * FROM assets WHERE id=? AND project_id=?", (asset_id, project_id))
        if not asset:
            raise RuntimeError("Audio asset not found")
        result = analyze_audio(Path(asset["storage_key"]))
        current_job = db._one("SELECT status FROM jobs WHERE id=?", (job_id,))
        if current_job and current_job["status"] == "cancelled":
            return
        db.update("jobs", job_id, {"status": "succeeded", "progress": 100, "logs": [{"at": utc_now(), "message": "Audio analysis complete", "analysis": result}], "finished_at": utc_now()})
        db.update("assets", asset_id, {"metadata": {**parse_json_fields(asset).get("metadata", {}), "analysis": result}})
    except Exception as exc:
        db.update("jobs", job_id, {"status": "failed", "progress": 100, "error_code": "ANALYSIS_FAILED", "error_message": str(exc), "finished_at": utc_now()})


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "app": settings.app_name, "ffmpeg": shutil.which("ffmpeg") is not None, "ffprobe": shutil.which("ffprobe") is not None}


@app.get("/api/providers")
async def providers() -> dict[str, Any]:
    result = {}
    for name, provider in provider_registry().items():
        result[name] = {"name": name, "model": provider.model, "capabilities": (await provider.capabilities()).__dict__}
    return {"default": settings.default_music_provider, "providers": result}


@app.get("/api/projects")
async def list_projects() -> list[dict[str, Any]]:
    return [project_response({**project, "assets": [], "lyrics": [], "versions": [], "jobs": [], "renders": []}) for project in db.list_projects()]


@app.post("/api/projects")
async def create_project(request: CreateProjectRequest) -> dict[str, Any]:
    now = utc_now()
    project = db.insert("projects", {"id": db.make_id("proj"), "title": request.title, "description": request.description, "creation_mode": request.creation_mode, "rights_confirmed": int(request.rights_confirmed), "status": "draft", "current_version_id": None, "created_at": now, "updated_at": now})
    return project_response({**project, "assets": [], "lyrics": [], "versions": [], "jobs": [], "renders": []})


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str) -> dict[str, Any]:
    project = db.project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project_response(project)


@app.post("/api/projects/{project_id}/assets")
async def upload_asset(project_id: str, file: UploadFile = File(...), role: str | None = Form(None)) -> dict[str, Any]:
    project = db.project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    target = safe_storage_path(project_id, file.filename or "upload")
    try:
        with target.open("wb") as handle:
            while chunk := await file.read(1024 * 1024):
                handle.write(chunk)
        metadata = validate_media(target, file.filename or "upload", file.content_type)
    except (MediaError, OSError) as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(400, str(exc)) from exc
    kind = metadata["kind"]
    asset_type = {"audio": "audio", "image": "image", "subtitle": "subtitle", "midi": "midi"}[kind]
    inferred_role = role or {"audio": "source_audio", "image": "cover", "subtitle": "lyrics_timing", "midi": "melody_midi"}[kind]
    asset = db.insert("assets", {"id": db.make_id("asset"), "project_id": project_id, "type": asset_type, "role": inferred_role, "storage_key": str(target), "original_filename": file.filename or target.name, "mime_type": file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream", "size": target.stat().st_size, "duration": metadata.get("duration"), "width": metadata.get("width"), "height": metadata.get("height"), "checksum": sha256_file(target), "metadata": metadata, "created_at": utc_now()})
    if asset_type == "subtitle":
        from packages.timeline.subtitles import parse_subtitles

        cues = parse_subtitles(target)
        text = "\n".join(cue.text for cue in cues)
        db.insert("lyrics", {"id": db.make_id("lyrics"), "project_id": project_id, "title": project["title"], "language": "und", "canonical_text": text, "structured_lyrics": [{"start_ms": cue.start_ms, "end_ms": cue.end_ms, "text": cue.text} for cue in cues], "source": asset_type, "created_at": utc_now()})
    db.update("projects", project_id, {"status": "assets_ready", "updated_at": utc_now()})
    return parse_json_fields({**asset, "url": asset_url(project_id, asset["id"])})


@app.get("/api/projects/{project_id}/assets/{asset_id}/download")
async def download_asset(project_id: str, asset_id: str) -> FileResponse:
    asset = db._one("SELECT * FROM assets WHERE id=? AND project_id=?", (asset_id, project_id))
    if not asset or not Path(asset["storage_key"]).exists():
        raise HTTPException(404, "Asset not found")
    return FileResponse(asset["storage_key"], media_type=asset["mime_type"], filename=asset["original_filename"])


@app.post("/api/projects/{project_id}/assets/{asset_id}/analyze")
async def analyze_asset(project_id: str, asset_id: str, background_tasks: BackgroundTasks) -> dict[str, Any]:
    asset = db._one("SELECT * FROM assets WHERE id=? AND project_id=?", (asset_id, project_id))
    if not asset:
        raise HTTPException(404, "Asset not found")
    if asset["type"] != "audio":
        raise HTTPException(400, "Only audio assets can be analyzed")
    job = create_job(project_id, "analyze_audio", "local")
    payload = {"kind": "analyze_audio", "project_id": project_id, "asset_id": asset_id, "job_id": job["id"]}
    try:
        await enqueue(payload)
    except QueueUnavailable:
        background_tasks.add_task(analyze_audio_job_sync, project_id, asset_id, job["id"])
    return {"job": parse_json_fields(job)}


@app.patch("/api/projects/{project_id}/lyrics/{lyrics_id}")
async def update_lyrics(project_id: str, lyrics_id: str, request: UpdateLyricsRequest) -> dict[str, Any]:
    lyric = db._one("SELECT * FROM lyrics WHERE id=? AND project_id=?", (lyrics_id, project_id))
    if not lyric:
        raise HTTPException(404, "Lyrics document not found")
    cues = [cue.model_dump() for cue in request.structured_lyrics]
    if any(cues[index]["start_ms"] < cues[index - 1]["start_ms"] for index in range(1, len(cues))):
        raise HTTPException(400, "Lyric cues must be ordered by start_ms")
    canonical_text = request.canonical_text if request.canonical_text is not None else "\n".join(cue["text"] for cue in cues)
    updated = db.update("lyrics", lyrics_id, {"canonical_text": canonical_text, "structured_lyrics": cues})
    db.update("projects", project_id, {"updated_at": utc_now()})
    return parse_json_fields(updated or lyric)


@app.get("/api/projects/{project_id}/lyrics/{lyrics_id}/export/{format_name}")
async def export_lyrics(project_id: str, lyrics_id: str, format_name: str) -> FileResponse:
    lyric = db._one("SELECT * FROM lyrics WHERE id=? AND project_id=?", (lyrics_id, project_id))
    if not lyric:
        raise HTTPException(404, "Lyrics document not found")
    if format_name not in {"txt", "lrc", "srt", "ass", "vtt"}:
        raise HTTPException(400, "Unsupported lyrics format")
    fields = parse_json_fields(lyric)
    cues = [Cue(int(item["start_ms"]), int(item["end_ms"]), item["text"], item.get("style", "Default")) for item in fields.get("structured_lyrics", [])]
    if format_name == "txt":
        content = fields.get("canonical_text", "") + "\n"
    elif format_name == "lrc":
        content = cues_to_lrc(cues)
    elif format_name == "srt":
        content = cues_to_srt(cues)
    elif format_name == "vtt":
        content = "WEBVTT\n\n" + cues_to_srt(cues).replace(",", ".")
    else:
        content = generate_ass(cues, 1080, 1080)
    output = settings.storage_root / project_id / "exports" / f"{lyrics_id}.{format_name}"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    media_type = "text/plain; charset=utf-8" if format_name != "ass" else "text/x-ass; charset=utf-8"
    return FileResponse(output, media_type=media_type, filename=f"lyrics.{format_name}")


@app.post("/api/projects/{project_id}/render")
async def start_render(project_id: str, request: RenderRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    project = db.project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if not asset_by_role(project, "audio"):
        raise HTTPException(400, "Upload an audio file before rendering")
    if request.resolution and request.resolution not in {f"{width}x{height}" for width, height in ASPECTS.values()}:
        raise HTTPException(400, "Unsupported resolution")
    now = utc_now()
    render = db.insert("renders", {"id": db.make_id("render"), "project_id": project_id, "template": request.template, "aspect_ratio": request.aspect_ratio, "resolution": request.resolution or f"{ASPECTS[request.aspect_ratio][0]}x{ASPECTS[request.aspect_ratio][1]}", "fps": request.fps, "status": "queued", "progress": 0, "output_asset_id": None, "config": request.model_dump(), "error": None, "created_at": now, "completed_at": None})
    job = create_job(project_id, "render_video", "local")
    payload = {"kind": "render_video", "project_id": project_id, "render_id": render["id"], "job_id": job["id"], "request": request.model_dump()}
    try:
        await enqueue(payload)
    except QueueUnavailable:
        background_tasks.add_task(render_job_sync, project_id, render["id"], job["id"], request.model_dump())
    db.update("projects", project_id, {"status": "rendering", "updated_at": now})
    return {"render": parse_json_fields(render), "job": parse_json_fields(job)}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    job = db._one("SELECT * FROM jobs WHERE id=?", (job_id,))
    if not job:
        raise HTTPException(404, "Job not found")
    return parse_json_fields(job)


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str) -> dict[str, Any]:
    job = db._one("SELECT * FROM jobs WHERE id=?", (job_id,))
    if not job:
        raise HTTPException(404, "Job not found")
    if job["status"] in {"queued", "running"}:
        db.update("jobs", job_id, {"status": "cancelled", "finished_at": utc_now(), "error_message": "Cancelled by user"})
        await mark_cancelled(job_id)
    return parse_json_fields(db._one("SELECT * FROM jobs WHERE id=?", (job_id,)) or job)


@app.post("/api/jobs/{job_id}/retry")
async def retry_job(job_id: str, background_tasks: BackgroundTasks) -> dict[str, Any]:
    job = db._one("SELECT * FROM jobs WHERE id=?", (job_id,))
    if not job:
        raise HTTPException(404, "Job not found")
    if job["status"] not in {"failed", "cancelled"}:
        raise HTTPException(409, "Only failed or cancelled jobs can be retried")
    await clear_cancelled(job_id)
    db.update("jobs", job_id, {"status": "queued", "progress": 0, "error_code": None, "error_message": None, "finished_at": None})
    if job["kind"] == "render_video":
        render = db._one("SELECT * FROM renders WHERE project_id=? ORDER BY created_at DESC LIMIT 1", (job["project_id"],))
        if not render:
            raise HTTPException(409, "Render record not found")
        request = json.loads(render["config"] or "{}")
        db.update("renders", render["id"], {"status": "queued", "progress": 0, "error": None, "completed_at": None})
        payload = {"kind": "render_video", "project_id": job["project_id"], "render_id": render["id"], "job_id": job_id, "request": request}
        try:
            await enqueue(payload)
        except QueueUnavailable:
            background_tasks.add_task(render_job_sync, job["project_id"], render["id"], job_id, request)
    elif job["kind"] == "analyze_audio":
        asset = db._one("SELECT id FROM assets WHERE project_id=? AND type='audio' ORDER BY created_at LIMIT 1", (job["project_id"],))
        if not asset:
            raise HTTPException(409, "Audio asset not found")
        payload = {"kind": "analyze_audio", "project_id": job["project_id"], "asset_id": asset["id"], "job_id": job_id}
        try:
            await enqueue(payload)
        except QueueUnavailable:
            background_tasks.add_task(analyze_audio_job_sync, job["project_id"], asset["id"], job_id)
    else:
        raise HTTPException(409, f"Retry is not implemented for job kind {job['kind']}")
    return parse_json_fields(db._one("SELECT * FROM jobs WHERE id=?", (job_id,)) or job)


@app.post("/api/projects/{project_id}/release-pack")
async def release_pack(project_id: str) -> dict[str, Any]:
    project = db.project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    root = settings.storage_root / project_id / "release"
    result = build_release_pack(project, settings.storage_root / project_id, root)
    row = db.insert("release_packs", {"id": db.make_id("release"), "project_id": project_id, "title": project["title"], "x_hook": f"{project['title']} — an original AI-assisted track from OpenMuse Studio", "x_copy": "See release/x-copy.txt", "description": project.get("description") or "", "hashtags": ["AIMusic"], "asset_manifest": result, "created_at": utc_now()})
    return {"release_pack": parse_json_fields(row), "files": result["files"]}


@app.get("/api/projects/{project_id}/manifest")
async def manifest(project_id: str) -> JSONResponse:
    project = db.project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    payload = project_response(project)
    payload["api_keys_included"] = False
    payload["manifest_version"] = "1"
    return JSONResponse(payload)


@app.post("/api/projects/{project_id}/edit-plan")
async def edit_plan(project_id: str, request: EditCommandRequest) -> dict[str, Any]:
    if not db.project(project_id):
        raise HTTPException(404, "Project not found")
    return mock_edit_plan(request.command).model_dump()


@app.get("/api/projects/{project_id}/release/{filename}")
async def release_file(project_id: str, filename: str) -> FileResponse:
    root = settings.storage_root / project_id / "release"
    path = (root / Path(filename).name).resolve()
    if root.resolve() not in path.parents or not path.exists():
        raise HTTPException(404, "Release file not found")
    return FileResponse(path)
