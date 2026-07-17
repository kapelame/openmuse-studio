from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import httpx
from PIL import Image, ImageDraw


@dataclass
class ImageResult:
    provider: str
    image_path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ImageProvider(Protocol):
    async def generate_cover(self, request: dict[str, Any]) -> ImageResult: ...
    async def edit_cover(self, request: dict[str, Any]) -> ImageResult: ...


class MockImageProvider:
    name = "mock"

    async def generate_cover(self, request: dict[str, Any]) -> ImageResult:
        output = Path(request.get("output", "mock-cover.png"))
        output.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (3000, 3000), "#d9d2c4")
        draw = ImageDraw.Draw(image)
        draw.rectangle((220, 220, 2780, 2780), outline="#24211e", width=12)
        draw.ellipse((950, 720, 2500, 2270), fill="#d96d52")
        image.save(output)
        return ImageResult(provider=self.name, image_path=output, metadata={"mock": True, "text_rendered": False})

    async def edit_cover(self, request: dict[str, Any]) -> ImageResult:
        return await self.generate_cover(request)


class CustomHTTPImageProvider:
    name = "custom-http"

    def __init__(self, endpoint: str, api_key: str = ""):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key

    async def generate_cover(self, request: dict[str, Any]) -> ImageResult:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(self.endpoint + "/generate-cover", headers=headers, json=request)
            response.raise_for_status()
            body = response.json()
        return ImageResult(provider=self.name, metadata=body)

    async def edit_cover(self, request: dict[str, Any]) -> ImageResult:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(self.endpoint + "/edit-cover", headers=headers, json=request)
            response.raise_for_status()
            body = response.json()
        return ImageResult(provider=self.name, metadata=body)
