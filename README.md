# OpenMuse Studio

Open-source AI music workspace for turning ideas, lyrics, demos, and songs into tracks, lyric videos, and release assets.

<p align="center">
  <a href="https://codespaces.new/kapelame/openmuse-studio?quickstart=1"><img src="https://github.com/codespaces/badge.svg" alt="Open in GitHub Codespaces" /></a>
  <a href="#docker-one-click"><img src="https://img.shields.io/badge/Run%20with%20Docker-2496ED?logo=docker&logoColor=white" alt="Run with Docker" /></a>
</p>

## What it does

- Create from text, lyrics, humming, demos, or finished songs.
- Align lyrics and render stable lyric videos with FFmpeg.
- Export MP4, subtitles, cover art, and project manifests.
- Run locally with Mock Provider; connect MiniMax when configured.

## Current Status

Implemented and runnable now:

- Next.js 16 web workspace with project list, asset upload, render controls, job polling and portable manifest download.
- FastAPI API with SQLite development persistence, project/assets/lyrics/jobs/renders/release-pack records, CORS and local storage.
- Media ingest for audio, images, subtitle formats and MIDI headers: size limits, probe validation, SHA-256 checksums, safe random storage names and original filenames in metadata.
- Song to MV vertical loop: upload audio + cover + SRT/LRC, generate ASS, render stable 1:1/16:9/9:16/4:5 MP4, generate contact sheet, verify streams and expose downloadable assets.
- Deterministic Editorial Lyrics template with 24/30fps only, center crop, no random motion, no rotation, no grain and low-alpha subtitle panel.
- FFmpeg + libass production path. When the local FFmpeg build lacks the `subtitles` filter, a transparent-static-overlay fallback keeps the actual video render in FFmpeg without generating the movie frame-by-frame in Pillow.
- Mock Music Provider, MiniMax Music Provider adapter, explicit capabilities, Mock Planner and release-pack manifest generation.
- Optional lightweight audio analysis: ffprobe metadata, waveform peaks, sample RMS and loudness-style signal. BPM, key, F0, MIDI, stems and chords stay optional/capability-gated.
- CLI commands for `analyze`, `align`, `render`, `pipeline` and release manifests.
- 17 automated tests covering parsers, media validation, provider capabilities, settings, rendering and API smoke flow.

Not included by default:

- Real local ASR/WhisperX alignment, Demucs stem separation and Basic Pitch MIDI extraction. Install optional extras and add workers before enabling them.
- A full multi-track DAW, word-level timeline editor, visual-story shot planner and true continuation/voice conversion.
- Redis + a standalone worker are implemented. The API falls back to FastAPI background tasks when Redis is unavailable; horizontal worker scaling, durable retries and process-level cancellation still need deployment hardening.
- Full S3/MinIO object-storage adapter. Local storage is the default; the service boundary is ready for an object store.

## Quick Start

Requirements: Python 3.11+, Node 20.9+, FFmpeg and ffprobe. The checked-in fixtures are generated sine audio and a geometric cover; no commercial music is included.

### One-Click Start

On macOS or Linux:

```bash
cd /Users/kape/openmuse-studio
./start.sh
```

The script creates `.env` when needed, syncs Python/Node dependencies, starts Redis through Docker when available, starts the API, starts the Redis worker, and starts or reuses the Web app. If Docker/Redis is unavailable, the API stays usable through its local BackgroundTasks fallback.

Useful commands:

```bash
./status.sh
./stop.sh
make start
make stop
```

If another local project already uses port 3000, choose a different web port without changing the API:

```bash
OPENMUSE_WEB_PORT=3001 ./start.sh
```

On macOS, double-click `OpenMuse.command` to start the workspace in Terminal.

首次在本地终端启动时，`start.sh` 会暂停一次询问是否现在配置 MiniMax。输入 API Key 时使用隐藏输入；选择 Mock 或直接回车即可跳过。非交互环境（Codespaces 自动钩子、CI、后台脚本）不会被这个问询阻塞。

需要重新打开安装问询时：

```bash
./start.sh --setup
```

### GitHub Codespaces

1. 点击仓库顶部的 **Open in GitHub Codespaces** 按钮。
2. 等待 Codespaces 完成初始化；`.devcontainer/post-create.sh` 会安装 FFmpeg、uv、Python 和前端依赖。
3. 初始化完成后会自动运行 `start.sh`，浏览器打开转发后的 3000 端口。

Codespaces 使用仓库内的 `.devcontainer/devcontainer.json`。网页默认通过同源 `/api` 访问 FastAPI，因此不需要把容器内的 `localhost:8000` 暴露给浏览器。Redis 不可用时仍会自动降级到 FastAPI 本地 BackgroundTasks。

### Docker One-Click

Docker Compose 不要求预先创建 `.env`，默认使用 Mock Provider 和本地可运行的配置：

```bash
docker compose up --build
```

打开 `http://localhost:3000`。这条命令会启动 Web、API、Worker、PostgreSQL、Redis 和 MinIO。要启用 MiniMax，在启动前把 `MINIMAX_API_KEY` 放进本地 `.env`；API Key 不会进入镜像或前端 bundle。

停止所有 Compose 服务：

```bash
docker compose down
```

如果本机的 3000 或 8000 已被占用，可只改宿主机端口：

```bash
OPENMUSE_WEB_PORT=3001 OPENMUSE_API_PORT=8001 docker compose up --build
```

```bash
cd /Users/kape/openmuse-studio
cp .env.example .env
make setup

# terminal 1
PYTHONPATH=apps/api:. uv run uvicorn openmuse_api.main:app --app-dir apps/api --reload

# terminal 2
npm --prefix apps/web run dev
```

Open `http://localhost:3000`. The API is at `http://localhost:8000/docs`.

Run the complete local render without starting the web app:

```bash
make render-demo
ffprobe -v error -show_format -show_streams -of json examples/rendered/mv.mp4
```

Docker services:

```bash
cp .env.example .env
docker compose up --build
```

This starts web, Redis worker, API, PostgreSQL, Redis and MinIO. SQLite/local storage is used by default for a zero-configuration development path; PostgreSQL and MinIO are service placeholders for deployment wiring.

## MiniMax Configuration

Set these only in `.env` or another secure runtime configuration:

```dotenv
MINIMAX_API_KEY=
MINIMAX_API_BASE=https://api.minimaxi.com
MINIMAX_MUSIC_MODEL=music-2.6
MINIMAX_COVER_MODEL=music-cover
DEFAULT_MUSIC_PROVIDER=minimax
```

The adapter targets the documented lyrics generation, music generation and music cover preprocess paths. It sends timeouts, handles non-2xx/base response errors, records trace IDs in returned metadata, retries 429/transient 5xx with exponential backoff, and never logs the Authorization header. URL outputs must be downloaded by the caller into project storage; hex output must pass strict decoding before being persisted.

The UI exposes MiniMax only when selected and still disables unsupported continuation, stems, voice conversion and other operations. Model names are environment-driven; the UI label “Music 3.0” is not used as an API model name.

## Runtime Settings

启动后可在左侧 `Providers` 或顶部 `Settings` 打开 Provider 设置面板，随时修改：

- Mock / MiniMax / Custom HTTP 默认 Provider
- MiniMax API Base、音乐模型和封面模型
- Custom HTTP endpoint
- 本地 ASR、Demucs、Basic Pitch 开关

设置写入本地 `.openmuse/settings.json`，文件会被 `.gitignore` 忽略并使用 `0600` 权限。MiniMax API Key 只允许写入或清除，不会回传给前端、写入数据库、项目 manifest 或普通日志。保存后新的任务立即使用新设置；已有运行中的任务不会被强行改写。

## Optional Audio Capabilities

The default install is CPU/lightweight:

```bash
uv sync
uv sync --extra asr       # faster-whisper
uv sync --extra audio-ml  # librosa, soundfile, Basic Pitch
uv sync --extra all
```

Do not enable optional models until the machine has appropriate disk, memory and license/data-policy review. The app must keep original audio and canonical lyrics; ASR is for finding timing and suggestions, not silent text replacement.

## Architecture

```text
apps/web                 Next.js workspace UI
apps/api/openmuse_api    FastAPI routes, SQLite records, local storage, background jobs
packages/timeline        Integer-millisecond LRC/SRT/VTT/ASS utilities
packages/providers       Provider protocol, Mock Provider, MiniMax adapter
workers                  Worker process boundary for queue-backed execution
templates                Editorial, album, kinetic and visual-story contracts
cli                      openmuse pipeline and render commands
tests                    Unit, API and media smoke tests
```

The pipeline is intentionally version-friendly:

```text
INGEST -> ANALYZE -> LYRICS -> GENERATE / TRANSFORM -> MIX -> COVER -> ALIGN -> SUBTITLE -> RENDER -> VALIDATE -> RELEASE PACK
```

Every render creates a new render record and output asset. Existing successful assets are not overwritten.

## CLI

```bash
openmuse analyze AUDIO
openmuse transcribe AUDIO
openmuse align AUDIO LYRICS
openmuse render --audio song.mp3 --cover cover.png --lyrics lyrics.srt --template editorial-lyrics --aspect 1:1 --output output/
openmuse pipeline --audio song.mp3 --cover cover.png --lyrics lyrics.srt --template editorial-lyrics --aspect 1:1 --output output/
```

The CLI and API call the same render and validation services. When no canonical lyrics or timing file is supplied, the CLI refuses to invent lyrics; install ASR separately and wire it into the worker path.

## Security, Rights and Privacy

The product must require confirmation that an uploaded demo/song is owned by the user or licensed for use. Do not add celebrity voice presets, watermark bypasses, copyright-identification bypasses or permission bypasses. Provider data policies may differ. API keys are runtime-only and excluded from `project.json`, release manifests and logs.

## Tests and Quality Gates

```bash
make test
make lint
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
make render-demo
```

The render QA checks codec, dimensions, frame rate, pixel format, audio stream presence and audio/video duration difference. The contact sheet is written beside the MP4. Static templates are expected to have zero visual motion apart from subtitle visibility changes.

## Roadmap

1. Harden Redis worker retry/cancellation semantics and add deployment observability.
2. Add optional ASR/WhisperX, canonical-lyrics forced alignment and a lightweight timeline editor with undo/redo.
3. Complete S3/MinIO storage, image providers, multi-ratio release exports and authenticated multi-user deployment.

## Contributing

Keep diffs small, preserve capability flags, add fixtures/tests for media behavior and run the full local render before opening a pull request. Never put API keys, copyrighted music or large model weights in the repository.
