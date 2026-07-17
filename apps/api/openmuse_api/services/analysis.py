from __future__ import annotations

import array
import json
import math
import subprocess
from pathlib import Path
from typing import Any


def analyze_audio(path: Path) -> dict[str, Any]:
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)], capture_output=True, text=True, check=False)
    if probe.returncode:
        raise RuntimeError(probe.stderr[-500:].strip())
    body = json.loads(probe.stdout or "{}")
    audio = next((stream for stream in body.get("streams", []) if stream.get("codec_type") == "audio"), {})
    duration = float(body.get("format", {}).get("duration") or audio.get("duration") or 0)
    decoded = subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "8000", "-f", "s16le", "pipe:1"], capture_output=True, check=False)
    samples = array.array("h")
    samples.frombytes(decoded.stdout)
    if samples and (samples.itemsize == 2 and __import__("sys").byteorder != "little"):
        samples.byteswap()
    peak = max((abs(sample) for sample in samples), default=0) / 32768
    rms = math.sqrt(sum(sample * sample for sample in samples) / max(len(samples), 1)) / 32768
    bucket_count = 96
    waveform = []
    for index in range(bucket_count):
        start = index * len(samples) // bucket_count
        end = max(start + 1, (index + 1) * len(samples) // bucket_count)
        waveform.append(round(max((abs(sample) for sample in samples[start:end]), default=0) / 32768, 4))
    return {
        "duration": duration,
        "channels": audio.get("channels"),
        "sample_rate": audio.get("sample_rate"),
        "bitrate": audio.get("bit_rate"),
        "codec": audio.get("codec_name"),
        "peak": round(peak, 5),
        "rms": round(rms, 5),
        "loudness": {"method": "sample_rms", "value": round(20 * math.log10(max(rms, 1e-9)), 2), "confidence": "medium"},
        "waveform_peaks": waveform,
        "bpm": None,
        "bpm_confidence": 0,
        "estimated_key": None,
        "key_confidence": 0,
        "silence_regions": [],
        "possible_song_sections": [],
        "optional_capabilities": {"f0": False, "midi": False, "stems": False, "chords": False},
        "notice": "BPM, key, F0, stems and chords require optional audio-ML extras; estimates are never presented as facts.",
    }
