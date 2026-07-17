from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Cue:
    start_ms: int
    end_ms: int
    text: str
    style: str = "Default"

    def __post_init__(self) -> None:
        self.start_ms = max(0, int(self.start_ms))
        self.end_ms = max(self.start_ms + 1, int(self.end_ms))


def timecode_to_ms(value: str) -> int:
    value = value.strip().replace(",", ".")
    parts = value.split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        hours = 0
    elif len(parts) == 3:
        hours, minutes, seconds = parts
    else:
        raise ValueError(f"Invalid timecode: {value}")
    whole, dot, fraction = seconds.partition(".")
    milliseconds = int((fraction + "000")[:3]) if dot else 0
    return (int(hours) * 3600 + int(minutes) * 60 + int(whole)) * 1000 + milliseconds


def ms_to_timecode(ms: int, comma: bool = False) -> str:
    ms = max(0, int(ms))
    hours, remainder = divmod(ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    separator = "," if comma else "."
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{millis:03d}"


def parse_lrc(text: str) -> list[Cue]:
    cues: list[tuple[int, str]] = []
    pattern = re.compile(r"\[(\d{1,2}:\d{2}(?:\.\d{1,3})?)\](.*)")
    for line in text.splitlines():
        matches = pattern.findall(line)
        for timestamp, value in matches:
            cues.append((timecode_to_ms(f"00:{timestamp}"), value.strip()))
    cues.sort(key=lambda item: item[0])
    return [Cue(start, cues[index + 1][0] if index + 1 < len(cues) else start + 4000, value) for index, (start, value) in enumerate(cues) if value]


def parse_srt(text: str) -> list[Cue]:
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip())
    cues: list[Cue] = []
    for block in blocks:
        lines = block.splitlines()
        if len(lines) < 2 or "-->" not in lines[1]:
            continue
        start, end = [item.strip() for item in lines[1].split("-->", 1)]
        value = "\n".join(lines[2:]).strip()
        if value:
            cues.append(Cue(timecode_to_ms(start), timecode_to_ms(end), value))
    return cues


def parse_vtt(text: str) -> list[Cue]:
    return parse_srt(re.sub(r"^WEBVTT\s*", "", text.strip(), flags=re.I))


def parse_subtitles(path: Path) -> list[Cue]:
    text = path.read_text(encoding="utf-8-sig")
    suffix = path.suffix.lower()
    if suffix == ".lrc":
        return parse_lrc(text)
    if suffix == ".vtt":
        return parse_vtt(text)
    if suffix in {".srt", ".ass"}:
        if suffix == ".ass":
            return parse_ass(text)
        return parse_srt(text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return [Cue(index * 4000, (index + 1) * 4000, line) for index, line in enumerate(lines)]


def parse_ass(text: str) -> list[Cue]:
    cues: list[Cue] = []
    for line in text.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        fields = line.removeprefix("Dialogue:").strip().split(",", 9)
        if len(fields) < 10:
            continue
        start, end, value = fields[1], fields[2], fields[9]
        value = re.sub(r"\{[^}]*\}", "", value).replace("\\N", "\n").strip()
        if value:
            cues.append(Cue(timecode_to_ms("00:" + start), timecode_to_ms("00:" + end), value, fields[0]))
    return cues


def wrap_lines(text: str, max_chars: int = 22) -> str:
    words = text.split()
    if len(text) <= max_chars:
        return text
    if not words:
        return text[:max_chars] + "\n" + text[max_chars:]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > max_chars:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return "\n".join(lines[:2])


def cues_to_lrc(cues: list[Cue]) -> str:
    return "\n".join(f"[{ms_to_timecode(cue.start_ms)[3:8]}.{cue.start_ms % 1000 // 10:02d}]{cue.text.replace(chr(10), ' ')}" for cue in cues) + "\n"


def cues_to_srt(cues: list[Cue]) -> str:
    blocks = []
    for index, cue in enumerate(cues, 1):
        blocks.append(f"{index}\n{ms_to_timecode(cue.start_ms, True)} --> {ms_to_timecode(cue.end_ms, True)}\n{cue.text}\n")
    return "\n".join(blocks)


def ass_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")


def generate_ass(cues: list[Cue], width: int, height: int, color: str = "#F4F0E8", alignment: str = "left", title: str | None = None) -> str:
    alignment_code = 1 if alignment == "left" else 2
    primary = "&H00" + color.removeprefix("#")[4:6] + color.removeprefix("#")[2:4] + color.removeprefix("#")[0:2]
    margin = round(width * 0.09)
    title_event = ""
    if title:
        title_event = f"Dialogue: 0,0:00:00.00,0:00:01.20,Title,,0,0,0,,{ass_escape(title)}\n"
    events = []
    for cue in cues:
        events.append(f"Dialogue: 0,{ms_to_timecode(cue.start_ms)[3:]},{ms_to_timecode(cue.end_ms)[3:]},Lyrics,,0,0,0,,{ass_escape(wrap_lines(cue.text))}")
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Lyrics,Arial,52,{primary},&H00FFFFFF,&H00000000,&H66000000,0,0,0,0,100,100,0,0,1,0,0.8,{alignment_code},{margin},{margin},{round(height * 0.12)},1
Style: Title,Arial,34,{primary},&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,{alignment_code},{margin},{margin},{round(height * 0.08)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
{title_event}{chr(10).join(events)}
"""
