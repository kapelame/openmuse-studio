from .base import MusicProvider, MusicProviderCapabilities
from .custom_http import CustomHTTPMusicProvider
from .image import CustomHTTPImageProvider, MockImageProvider
from .mock import MockMusicProvider
from .minimax import MiniMaxLyricsProvider, MiniMaxMusicProvider
from .registry import ProviderRegistry

__all__ = ["MusicProvider", "MusicProviderCapabilities", "MockMusicProvider", "MiniMaxMusicProvider", "MiniMaxLyricsProvider", "CustomHTTPMusicProvider", "MockImageProvider", "CustomHTTPImageProvider", "ProviderRegistry"]
