from packages.providers.base import MusicProvider
from packages.providers.custom_http import CustomHTTPMusicProvider
from packages.providers.image import CustomHTTPImageProvider, MockImageProvider
from packages.providers.minimax import MiniMaxMusicProvider
from packages.providers.mock import MockMusicProvider
from packages.providers.registry import ProviderRegistry

from ..config import reload_runtime_settings, settings


registry = ProviderRegistry()
_registry_signature: tuple[object, ...] | None = None


def refresh_provider_registry() -> ProviderRegistry:
    global registry, _registry_signature
    reload_runtime_settings()
    signature = (
        settings.minimax_api_key,
        settings.minimax_api_base,
        settings.minimax_music_model,
        settings.minimax_cover_model,
        settings.custom_music_endpoint,
        settings.custom_image_endpoint,
    )
    if signature == _registry_signature:
        return registry

    next_registry = ProviderRegistry()
    next_registry.register("music", "mock", MockMusicProvider())
    next_registry.register(
        "music",
        "minimax",
        MiniMaxMusicProvider(
            settings.minimax_api_key,
            settings.minimax_api_base,
            settings.minimax_music_model,
            settings.minimax_cover_model,
        ),
    )
    next_registry.register("image", "mock", MockImageProvider())
    if settings.custom_music_endpoint:
        next_registry.register("music", "custom-http", CustomHTTPMusicProvider(settings.custom_music_endpoint))
    if settings.custom_image_endpoint:
        next_registry.register("image", "custom-http", CustomHTTPImageProvider(settings.custom_image_endpoint))
    registry = next_registry
    _registry_signature = signature
    return registry


def music_provider() -> MusicProvider:
    return refresh_provider_registry().get("music", settings.default_music_provider)


def provider_registry(kind: str = "music") -> dict[str, MusicProvider]:
    return refresh_provider_registry().all(kind)
