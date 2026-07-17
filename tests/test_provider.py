import asyncio
from pathlib import Path

from packages.providers.base import GenerationRequest
from packages.providers.minimax import decode_hex_audio, extract_audio_value
from packages.providers.mock import MockMusicProvider
from packages.providers.registry import ProviderRegistry


def test_mock_capabilities_are_explicit() -> None:
    capabilities = asyncio.run(MockMusicProvider().capabilities())
    assert capabilities.text_to_music is True
    assert capabilities.continuation is False
    assert capabilities.stems is False


def test_hex_audio_decoder(tmp_path: Path) -> None:
    output = decode_hex_audio("52494646", tmp_path / "audio.bin")
    assert output.read_bytes() == b"RIFF"


def test_minimax_audio_response_parser() -> None:
    assert extract_audio_value({"data": {"audio": "52494646"}}) == ("hex", "52494646")
    assert extract_audio_value({"data": {"audio_url": "https://example.test/a.mp3"}}) == ("url", "https://example.test/a.mp3")


def test_provider_registry_is_dynamic() -> None:
    registry = ProviderRegistry()
    registry.register("music", "fixture", object())
    assert "fixture" in registry.all("music")
    registry.unregister("music", "fixture")
    assert "fixture" not in registry.all("music")
