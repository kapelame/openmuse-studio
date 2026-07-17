from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class MusicProviderCapabilities:
    text_to_music: bool = False
    lyrics_to_music: bool = False
    instrumental_generation: bool = False
    reference_audio: bool = False
    cover: bool = False
    continuation: bool = False
    melody_conditioning: bool = False
    midi_conditioning: bool = False
    replace_lyrics: bool = False
    stems: bool = False
    streaming: bool = False
    url_output: bool = False
    hex_output: bool = False


@dataclass
class GenerationRequest:
    prompt: str = ""
    lyrics: str = ""
    title: str = "Untitled"
    instrumental: bool = False
    reference_audio: Path | None = None
    operation: str = "generate"
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationResult:
    provider: str
    model: str
    audio_path: Path | None = None
    lyrics: str | None = None
    provider_job_id: str | None = None
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LyricsResult:
    provider: str
    title: str
    lyrics: str
    style_tags: str = ""
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class MusicProvider(Protocol):
    name: str
    model: str

    async def capabilities(self) -> MusicProviderCapabilities: ...
    async def generate_song(self, request: GenerationRequest) -> GenerationResult: ...
    async def cover_song(self, request: GenerationRequest) -> GenerationResult: ...
    async def preprocess_reference(self, request: GenerationRequest) -> dict[str, Any]: ...
    async def get_job(self, job_id: str) -> dict[str, Any]: ...
    async def cancel_job(self, job_id: str) -> None: ...


class LyricsProvider(Protocol):
    async def write_full_song(self, prompt: str, title: str | None = None) -> LyricsResult: ...
    async def edit_lyrics(self, prompt: str, lyrics: str, title: str | None = None) -> LyricsResult: ...
