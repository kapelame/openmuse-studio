from pathlib import Path

from apps.api.openmuse_api.services.release import build_release_pack


def test_release_pack_materializes_publish_files(tmp_path: Path) -> None:
    project = {
        "id": "release-test",
        "title": "Fixture Song",
        "description": "A fixture release",
        "assets": [
            {"type": "audio", "role": "source_audio", "storage_key": "examples/demo-tone.wav"},
            {"type": "image", "role": "cover", "storage_key": "examples/demo-cover.png"},
            {"type": "subtitle", "role": "lyrics_timing", "storage_key": "examples/demo.srt"},
        ],
    }
    result = build_release_pack(project, Path("examples"), tmp_path / "release")
    assert (tmp_path / "release/song.wav").exists()
    assert (tmp_path / "release/song.mp3").exists()
    assert (tmp_path / "release/cover-3000.png").exists()
    assert (tmp_path / "release/lyrics.ass").exists()
    assert "song.wav" in result["files"]
