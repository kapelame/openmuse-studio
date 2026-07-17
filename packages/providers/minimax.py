from __future__ import annotations

import asyncio
import base64
import binascii
import json
from pathlib import Path
from typing import Any

import httpx

from .base import GenerationRequest, GenerationResult, LyricsResult, MusicProviderCapabilities


class MiniMaxAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, trace_id: str | None = None, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.trace_id = trace_id
        self.retryable = retryable


class MiniMaxMusicProvider:
    name = "minimax"

    def __init__(self, api_key: str, api_base: str, music_model: str, cover_model: str, timeout: float = 90.0):
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.model = music_model
        self.cover_model = cover_model
        self.timeout = timeout

    async def capabilities(self) -> MusicProviderCapabilities:
        # These flags describe the implemented API surface; unsupported features stay false.
        return MusicProviderCapabilities(text_to_music=True, lyrics_to_music=True, instrumental_generation=True, reference_audio=True, cover=True, url_output=True, hex_output=True)

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise MiniMaxAPIError("MINIMAX_API_KEY is not configured")
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        last_error: MiniMaxAPIError | None = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(self.api_base + path, headers=headers, json=payload)
                body = response.json() if response.content else {}
                base_resp = body.get("base_resp") or {}
                trace_id = body.get("trace_id") or base_resp.get("trace_id")
                if response.status_code >= 400 or base_resp.get("status_code", 0) not in (0, None):
                    status = response.status_code
                    retryable = status == 429 or status >= 500
                    last_error = MiniMaxAPIError(base_resp.get("status_msg") or body.get("message") or response.text[:500], status, trace_id, retryable)
                    if retryable and attempt < 2:
                        await asyncio.sleep(2**attempt)
                        continue
                    raise last_error
                body["_trace_id"] = trace_id
                return body
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = MiniMaxAPIError(str(exc), retryable=True)
                if attempt < 2:
                    await asyncio.sleep(2**attempt)
                    continue
                raise last_error from exc
        raise last_error or MiniMaxAPIError("MiniMax request failed")

    async def generate_song(self, request: GenerationRequest) -> GenerationResult:
        payload = {"model": self.model, "prompt": request.prompt, "lyrics": request.lyrics, "stream": False, "output_format": request.parameters.get("output_format", "url"), "lyrics_optimizer": request.parameters.get("lyrics_optimizer", True), "is_instrumental": request.instrumental}
        if request.parameters.get("audio_setting"):
            payload["audio_setting"] = request.parameters["audio_setting"]
        if request.parameters.get("cover_feature_id"):
            payload["cover_feature_id"] = request.parameters["cover_feature_id"]
        if request.reference_audio:
            payload["audio_base64"] = base64.b64encode(request.reference_audio.read_bytes()).decode("ascii")
        body = await self._post("/v1/music_generation", payload)
        data = body.get("data") or body.get("result") or body
        return GenerationResult(provider=self.name, model=self.model, provider_job_id=data.get("task_id") or data.get("id"), trace_id=body.get("_trace_id"), lyrics=data.get("lyrics"), metadata=data)

    async def cover_song(self, request: GenerationRequest) -> GenerationResult:
        payload = {"model": self.cover_model, "prompt": request.prompt or "A faithful cover with a refreshed arrangement", "lyrics": request.lyrics, "stream": False, "output_format": request.parameters.get("output_format", "url")}
        if request.parameters.get("cover_feature_id"):
            payload["cover_feature_id"] = request.parameters["cover_feature_id"]
        elif request.reference_audio:
            payload["audio_base64"] = base64.b64encode(request.reference_audio.read_bytes()).decode("ascii")
        body = await self._post("/v1/music_generation", payload)
        data = body.get("data") or body.get("result") or body
        return GenerationResult(provider=self.name, model=self.cover_model, provider_job_id=data.get("task_id") or data.get("id"), trace_id=body.get("_trace_id"), lyrics=data.get("lyrics"), metadata=data)

    async def preprocess_reference(self, request: GenerationRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": self.cover_model}
        if request.parameters.get("audio_url"):
            payload["audio_url"] = request.parameters["audio_url"]
        elif request.reference_audio:
            payload["audio_base64"] = base64.b64encode(request.reference_audio.read_bytes()).decode("ascii")
        else:
            raise MiniMaxAPIError("Music cover preprocess requires audio_url or reference_audio")
        return await self._post("/v1/music_cover_preprocess", payload)

    async def get_job(self, job_id: str) -> dict[str, Any]:
        return {"id": job_id, "status": "provider_status_unavailable", "reason": "MiniMax music generation is consumed as a synchronous response in this adapter."}

    async def cancel_job(self, job_id: str) -> None:
        raise MiniMaxAPIError("MiniMax cancellation is not exposed by this adapter")


class MiniMaxLyricsProvider:
    name = "minimax"

    def __init__(self, music_provider: MiniMaxMusicProvider):
        self.music_provider = music_provider

    async def write_full_song(self, prompt: str, title: str | None = None) -> LyricsResult:
        body = await self.music_provider._post("/v1/lyrics_generation", {"mode": "write_full_song", "prompt": prompt, **({"title": title} if title else {})})
        return LyricsResult(provider=self.name, title=body.get("song_title") or title or "Untitled", lyrics=body.get("lyrics", ""), style_tags=body.get("style_tags", ""), trace_id=body.get("_trace_id"), metadata=body)

    async def edit_lyrics(self, prompt: str, lyrics: str, title: str | None = None) -> LyricsResult:
        body = await self.music_provider._post("/v1/lyrics_generation", {"mode": "edit", "prompt": prompt, "lyrics": lyrics, **({"title": title} if title else {})})
        return LyricsResult(provider=self.name, title=body.get("song_title") or title or "Untitled", lyrics=body.get("lyrics", ""), style_tags=body.get("style_tags", ""), trace_id=body.get("_trace_id"), metadata=body)


def decode_hex_audio(value: str, output: Path) -> Path:
    try:
        if not value or len(value) % 2 or any(char not in "0123456789abcdefABCDEF" for char in value):
            raise ValueError("not valid hexadecimal")
        output.write_bytes(binascii.unhexlify(value))
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"Invalid hex audio: {exc}") from exc
    return output


def extract_audio_value(payload: dict[str, Any]) -> tuple[str, str] | None:
    """Find a URL or hex audio value in common MiniMax response shapes without guessing at one fixed wrapper."""
    candidates = [payload, payload.get("data") or {}, payload.get("result") or {}]
    for item in candidates:
        if not isinstance(item, dict):
            continue
        for key in ("audio_url", "url"):
            value = item.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return "url", value
        for key in ("audio", "audio_hex", "hex_audio", "audio_data"):
            value = item.get(key)
            if isinstance(value, str) and value:
                return "hex", value
    return None


async def materialize_audio(payload: dict[str, Any], output: Path, timeout: float = 90.0) -> Path:
    """Download expiring URL output immediately or decode hex output into project storage."""
    extracted = extract_audio_value(payload)
    if not extracted:
        raise MiniMaxAPIError("MiniMax response did not include audio output")
    kind, value = extracted
    if kind == "hex":
        return decode_hex_audio(value, output)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(value)
        response.raise_for_status()
        output.write_bytes(response.content)
    return output
