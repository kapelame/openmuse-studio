import json
from pathlib import Path

from apps.api.openmuse_api.services.render import render_video


def test_render_has_stable_output(tmp_path: Path) -> None:
    output = tmp_path / "mv.mp4"
    result = render_video("test", "render", Path("examples/demo-tone.wav"), Path("examples/demo-cover.png"), Path("examples/demo.srt"), {"aspect_ratio": "1:1", "fps": 24, "subtitle_alignment": "left"}, output)
    assert output.exists()
    assert result["width"] == 1080 and result["height"] == 1080
    assert result["fps"] == "24/1"
    assert result["video_codec"] == "h264" and result["audio_codec"] == "aac"
    assert abs(result["duration"] - 12.0) < 0.15
