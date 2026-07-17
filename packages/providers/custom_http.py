from __future__ import annotations

from typing import Any

import httpx

from .base import GenerationRequest, GenerationResult, MusicProviderCapabilities


class CustomHTTPMusicProvider:
    name = "custom-http"

    def __init__(self, endpoint: str, model: str = "custom", api_key: str = "", capabilities: MusicProviderCapabilities | None = None):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.api_key = api_key
        self._capabilities = capabilities or MusicProviderCapabilities(text_to_music=True, lyrics_to_music=True, url_output=True)

    async def capabilities(self) -> MusicProviderCapabilities:
        return self._capabilities

    async def generate_song(self, request: GenerationRequest) -> GenerationResult:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(self.endpoint + "/generate", headers=headers, json={"model": self.model, "prompt": request.prompt, "lyrics": request.lyrics, "instrumental": request.instrumental, "parameters": request.parameters})
            response.raise_for_status()
            body = response.json()
        return GenerationResult(provider=self.name, model=self.model, provider_job_id=body.get("job_id"), lyrics=body.get("lyrics"), metadata=body)

    async def cover_song(self, request: GenerationRequest) -> GenerationResult:
        if not self._capabilities.cover:
            raise RuntimeError("Custom provider has not declared cover capability")
        request.parameters["operation"] = "cover"
        return await self.generate_song(request)

    async def preprocess_reference(self, request: GenerationRequest) -> dict[str, Any]:
        if not self._capabilities.reference_audio:
            raise RuntimeError("Custom provider has not declared reference_audio capability")
        return {"reference_audio": str(request.reference_audio) if request.reference_audio else None}

    async def get_job(self, job_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(self.endpoint + f"/jobs/{job_id}")
            response.raise_for_status()
            return response.json()

    async def cancel_job(self, job_id: str) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(self.endpoint + f"/jobs/{job_id}/cancel")
            response.raise_for_status()
