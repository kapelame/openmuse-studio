from pathlib import Path

from apps.api.openmuse_api.services.media import safe_storage_path, sha256_file, validate_media


def test_fixture_media_is_real() -> None:
    audio = Path("examples/demo-tone.wav")
    cover = Path("examples/demo-cover.png")
    audio_info = validate_media(audio, audio.name)
    cover_info = validate_media(cover, cover.name)
    assert audio_info["kind"] == "audio" and audio_info["duration"] == 12.0
    assert cover_info["kind"] == "image" and cover_info["width"] == 1080
    assert len(sha256_file(audio)) == 64


def test_storage_path_drops_traversal() -> None:
    path = safe_storage_path("project", "../../dangerous file.wav")
    assert path.name.endswith("dangerous_file.wav")
    assert ".." not in path.name
