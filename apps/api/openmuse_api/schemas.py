from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator


class CreateProjectRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = ""
    creation_mode: Literal["text", "lyrics", "hum", "demo", "mv"] = "mv"
    rights_confirmed: bool = False

    @model_validator(mode="after")
    def require_rights_confirmation(self) -> "CreateProjectRequest":
        if not self.rights_confirmed:
            raise ValueError("Confirm that you own the material or have permission to use it")
        return self


class RenderRequest(BaseModel):
    template: Literal["album-cover", "editorial-lyrics", "kinetic-lyrics", "visual-story"] = "editorial-lyrics"
    aspect_ratio: Literal["1:1", "16:9", "9:16", "4:5"] = "1:1"
    resolution: str | None = None
    fps: Literal[24, 30] = 24
    title: str | None = None
    subtitle_color: str = "#F4F0E8"
    subtitle_alignment: Literal["left", "center"] = "left"
    ken_burns: bool = False


class EditCommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=1000)


class LyricCueRequest(BaseModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=500)
    style: str = "Default"

    @model_validator(mode="after")
    def valid_range(self) -> "LyricCueRequest":
        if self.start_ms >= self.end_ms:
            raise ValueError("start_ms must be less than end_ms")
        return self


class UpdateLyricsRequest(BaseModel):
    structured_lyrics: list[LyricCueRequest]
    canonical_text: str | None = None


class Capabilities(BaseModel):
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


class EditPlan(BaseModel):
    intent: str
    preserve: list[str]
    changes: dict[str, Any]
    jobs: list[str]
    requires_confirmation: bool = True
