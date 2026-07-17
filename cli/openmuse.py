from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from apps.api.openmuse_api.services.media import validate_media
from apps.api.openmuse_api.services.render import ASPECTS, make_contact_sheet, probe, render_video


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="openmuse", description="OpenMuse Studio command line tools")
    sub = root.add_subparsers(dest="command", required=True)
    for name in ("analyze", "transcribe"):
        item = sub.add_parser(name); item.add_argument("audio")
    align = sub.add_parser("align"); align.add_argument("audio"); align.add_argument("lyrics")
    music = sub.add_parser("music"); music.add_argument("action", choices=["generate", "cover"])
    render = sub.add_parser("render"); render.add_argument("--audio", required=True); render.add_argument("--cover", required=True); render.add_argument("--lyrics"); render.add_argument("--template", default="editorial-lyrics"); render.add_argument("--aspect", default="1:1", choices=list(ASPECTS)); render.add_argument("--output", required=True)
    release = sub.add_parser("release-pack"); release.add_argument("--project", required=True); release.add_argument("--output", required=True)
    pipeline = sub.add_parser("pipeline"); pipeline.add_argument("--audio", required=True); pipeline.add_argument("--cover", required=True); pipeline.add_argument("--lyrics"); pipeline.add_argument("--template", default="editorial-lyrics"); pipeline.add_argument("--aspect", default="1:1", choices=list(ASPECTS)); pipeline.add_argument("--output", required=True)
    lyrics = sub.add_parser("lyrics"); lyrics.add_argument("action", choices=["generate"])
    return root


def main() -> None:
    args = parser().parse_args()
    if args.command in {"analyze", "transcribe", "align"}:
        path = Path(args.audio)
        print(json.dumps(validate_media(path, path.name), indent=2))
        if args.command == "transcribe":
            print("ASR is optional. Install with: uv sync --extra asr")
        if args.command == "align":
            print("Alignment service is capability-gated; canonical lyric text is never replaced silently.")
        return
    if args.command == "render":
        output = Path(args.output)
        result = render_video("cli", "cli-render", Path(args.audio), Path(args.cover), Path(args.lyrics) if args.lyrics else None, {"template": args.template, "aspect_ratio": args.aspect, "fps": 24, "subtitle_alignment": "left"}, output / "mv.mp4")
        make_contact_sheet(output / "mv.mp4", output / "contact-sheet.jpg")
        print(json.dumps(result, indent=2))
        return
    if args.command == "pipeline":
        output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
        print(json.dumps({"step": "INGEST", "audio": validate_media(Path(args.audio), Path(args.audio).name)}, indent=2))
        result = render_video("cli", "pipeline", Path(args.audio), Path(args.cover), Path(args.lyrics) if args.lyrics else None, {"template": args.template, "aspect_ratio": args.aspect, "fps": 24, "subtitle_alignment": "left"}, output / "mv.mp4")
        make_contact_sheet(output / "mv.mp4", output / "contact-sheet.jpg")
        (output / "project.json").write_text(json.dumps({"pipeline": ["INGEST", "ANALYZE", "ALIGN", "SUBTITLE", "RENDER", "VALIDATE"], "render": result, "api_keys_included": False}, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(output), "render": result}, indent=2))
        return
    if args.command in {"music", "lyrics"}:
        print("This command is exposed as a provider hook. Configure a provider in the Web API for generation.")
        return
    if args.command == "release-pack":
        source = json.loads(Path(args.project).read_text(encoding="utf-8"))
        output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
        (output / "project.json").write_text(json.dumps({"project": source, "api_keys_included": False}, indent=2), encoding="utf-8")
        print(f"Release manifest written to {output}")


if __name__ == "__main__":
    main()
