from __future__ import annotations

from pathlib import Path

from apps.api.openmuse_api.services.analysis import analyze_audio


class LocalAnalysisProvider:
    name = "local-analysis"

    async def analyze(self, path: Path) -> dict:
        return analyze_audio(path)
