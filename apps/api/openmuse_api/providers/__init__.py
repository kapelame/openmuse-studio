from packages.providers.base import MusicProvider
from packages.providers.custom_http import CustomHTTPMusicProvider
from packages.providers.image import CustomHTTPImageProvider, MockImageProvider
from packages.providers.minimax import MiniMaxMusicProvider
from packages.providers.mock import MockMusicProvider
from packages.providers.registry import ProviderRegistry

from ..config import settings


def music_provider() -> MusicProvider:
    if settings.default_music_provider == "minimax":
        return MiniMaxMusicProvider(settings.minimax_api_key, settings.minimax_api_base, settings.minimax_music_model, settings.minimax_cover_model)
    return MockMusicProvider()


registry = ProviderRegistry()
registry.register("music", "mock", MockMusicProvider())
registry.register("music", "minimax", MiniMaxMusicProvider(settings.minimax_api_key, settings.minimax_api_base, settings.minimax_music_model, settings.minimax_cover_model))
registry.register("image", "mock", MockImageProvider())
if settings.custom_music_endpoint:
    registry.register("music", "custom-http", CustomHTTPMusicProvider(settings.custom_music_endpoint))
if settings.custom_image_endpoint:
    registry.register("image", "custom-http", CustomHTTPImageProvider(settings.custom_image_endpoint))


def provider_registry() -> dict[str, MusicProvider]:
    return registry.all("music")
