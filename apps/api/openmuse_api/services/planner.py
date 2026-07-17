from __future__ import annotations

import re

from ..schemas import EditPlan


def mock_edit_plan(command: str) -> EditPlan:
    text = command.lower()
    if any(word in text for word in ("字幕", "subtitle", "歌词")):
        changes = {"subtitle_alignment": "left" if "左" in command or "left" in text else "center", "font_weight": "regular", "outline": 0, "motion": "none"}
        return EditPlan(intent="update_video_style", preserve=["audio", "lyrics_timing", "cover"], changes=changes, jobs=["regenerate_ass", "render_video", "validate_video"])
    if "封面" in command or "cover" in text:
        return EditPlan(intent="update_cover", preserve=["audio", "lyrics", "lyrics_timing", "video_template"], changes={"visual_prompt": command}, jobs=["generate_cover", "render_video", "validate_video"])
    if "方形" in command or "square" in text or "1:1" in text:
        return EditPlan(intent="update_video_aspect", preserve=["audio", "lyrics", "cover"], changes={"aspect_ratio": "1:1"}, jobs=["render_video", "validate_video"])
    return EditPlan(intent="interpret_request", preserve=["existing_assets"], changes={"prompt": command}, jobs=["review_plan"])
