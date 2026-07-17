from __future__ import annotations

from collections import defaultdict
from typing import Any


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, dict[str, Any]] = defaultdict(dict)

    def register(self, kind: str, name: str, provider: Any) -> None:
        self._providers[kind][name] = provider

    def unregister(self, kind: str, name: str) -> None:
        self._providers[kind].pop(name, None)

    def get(self, kind: str, name: str) -> Any:
        try:
            return self._providers[kind][name]
        except KeyError as exc:
            raise KeyError(f"Unknown {kind} provider: {name}") from exc

    def all(self, kind: str) -> dict[str, Any]:
        return dict(self._providers[kind])
