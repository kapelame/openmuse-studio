from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from .base import GenerationRequest, GenerationResult, MusicProviderCapabilities


class MockMusicProvider:
    name = "mock"
    model = "mock-tone-v1"

    async def capabilities(self) -> MusicProviderCapabilities:
        return MusicProviderCapabilities(text_to_music=True, lyrics_to_music=True, instrumental_generation=True, reference_audio=True, cover=True, url_output=False, hex_output=False)

    async def generate_song(self, request: GenerationRequest) -> GenerationResult:
        output = Path(request.parameters.get("output_dir", ".")) / "mock-song.wav"
        output.parent.mkdir(parents=True, exist_ok=True)
        # A deterministic short tone bed makes the provider useful for CI and demos without pretending to be a music model.
        subprocess.run(["ffmpeg", "-hide_banner", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=12", "-af", "volume=0.16", "-ar", "44100", "-ac", "2", str(output)], capture_output=True, check=True)
        await asyncio.sleep(0)
        return GenerationResult(provider=self.name, model=self.model, audio_path=output, lyrics=request.lyrics or None, metadata={"mock": True, "notice": "Deterministic tone fixture; replace with a real provider for music generation."})

    async def cover_song(self, request: GenerationRequest) -> GenerationResult:
        return await self.generate_song(request)

    async def preprocess_reference(self, request: GenerationRequest) -> dict:
        return {"provider": self.name, "supported": False, "reason": "Mock provider only validates the workflow."}

    async def get_job(self, job_id: str) -> dict:
        return {"id": job_id, "status": "succeeded"}

    async def cancel_job(self, job_id: str) -> None:
        return None
