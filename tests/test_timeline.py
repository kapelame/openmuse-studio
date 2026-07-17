from packages.timeline.subtitles import Cue, cues_to_lrc, cues_to_srt, generate_ass, ms_to_timecode, parse_lrc, parse_srt, timecode_to_ms, wrap_lines
from packages.timeline.crop import calculate_center_crop


def test_timecode_round_trip() -> None:
    assert timecode_to_ms("01:02:03,450") == 3_723_450
    assert ms_to_timecode(3_723_450, comma=True) == "01:02:03,450"


def test_lrc_and_srt_parsers() -> None:
    lrc = parse_lrc("[00:01.20]First line\n[00:04.50]Second line")
    assert lrc[0].start_ms == 1200 and lrc[0].end_ms == 4500
    srt = parse_srt("1\n00:00:00,000 --> 00:00:02,100\nHello\n")
    assert srt == [Cue(0, 2100, "Hello")]


def test_exports_and_ass() -> None:
    cues = [Cue(0, 2100, "Hello world"), Cue(2100, 4000, "Second line")]
    assert "[00:00.00]" in cues_to_lrc(cues)
    assert "00:00:00,000 --> 00:00:02,100" in cues_to_srt(cues)
    ass = generate_ass(cues, 1080, 1080)
    assert "PlayResX: 1080" in ass and "Dialogue:" in ass


def test_line_breaking() -> None:
    assert "\n" in wrap_lines("one two three four five six seven", 12)


def test_safe_crop_calculation() -> None:
    assert calculate_center_crop(1920, 1080, 1080, 1080) == (420, 0, 1500, 1080)
    assert calculate_center_crop(1080, 1920, 1080, 1080) == (0, 420, 1080, 1500)
