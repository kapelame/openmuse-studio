# OpenMuse Studio

Open-source AI music workspace for songs, lyrics, cover art, and music videos.

<p align="center">
  <a href="https://codespaces.new/kapelame/openmuse-studio?quickstart=1"><img src="https://github.com/codespaces/badge.svg" alt="Open in GitHub Codespaces" /></a>
  <a href="#quick-start"><img src="https://img.shields.io/badge/Start%20with-Docker-2496ED?logo=docker&logoColor=white" alt="Start with Docker" /></a>
</p>

OpenMuse turns an idea, demo, song, or lyrics into a working project with audio, synchronized lyrics, cover art, and lyric videos.

## Status

Working now:

- Create projects and upload audio, images, and SRT/LRC lyrics.
- Render stable lyric videos in 1:1, 16:9, 9:16, and 4:5 formats.
- Export MP4, SRT, ASS, project manifests, and contact sheets.
- Track asynchronous jobs with progress, logs, retry, and cancellation.
- Use the Mock Provider without API keys.
- Configure MiniMax or a custom HTTP provider at runtime.
- Run the same pipeline from the web app or the `openmuse` CLI.

Not included by default:

- Large local models such as faster-whisper, WhisperX, Demucs, and Basic Pitch.
- Full multi-track DAW editing, voice conversion, and provider features that are not exposed by the selected provider.
- Production authentication, billing, and multi-user storage.

## Quick Start

### GitHub Codespaces

Click **Open in GitHub Codespaces** above. The development container installs the dependencies and starts the app.

### Local

Requirements: Python 3.11+, Node 20.9+, FFmpeg, and `ffprobe`.

```bash
git clone https://github.com/kapelame/openmuse-studio.git
cd openmuse-studio
./start.sh
```

Open <http://localhost:3000>.

On first launch, the terminal asks whether to configure MiniMax. Press Enter to use the Mock Provider. Reopen the setup flow later with:

```bash
./start.sh --setup
```

### Docker

```bash
docker compose up --build
```

Open <http://localhost:3000>. Stop the stack with:

```bash
docker compose down
```

Use another port when needed:

```bash
OPENMUSE_WEB_PORT=3001 OPENMUSE_API_PORT=8001 docker compose up --build
```

## MiniMax

Configure MiniMax during setup, from the **Providers** panel, or with environment variables:

```dotenv
MINIMAX_API_KEY=
MINIMAX_API_BASE=https://api.minimaxi.com
MINIMAX_MUSIC_MODEL=music-3.0
MINIMAX_COVER_MODEL=music-cover
DEFAULT_MUSIC_PROVIDER=minimax
```

The model is configurable and is never hard-coded into the frontend. Temporary provider URLs are downloaded into project storage. API keys are not sent to the frontend or included in manifests and logs.

Provider capabilities are explicit. Unsupported operations such as continuation, melody conditioning, stems, or voice conversion are disabled instead of being simulated with a different API.

## Runtime Settings

Open **Settings** in the app to change:

- Music and image providers.
- MiniMax API base URL and model names.
- Custom HTTP endpoints.
- Optional ASR, Demucs, and Basic Pitch features.

Settings are stored locally in `.openmuse/settings.json` with file mode `0600`. The file is ignored by Git.

## CLI

```bash
openmuse analyze AUDIO
openmuse transcribe AUDIO
openmuse align AUDIO LYRICS
openmuse render --audio song.mp3 --cover cover.png --lyrics lyrics.srt --output output/
openmuse pipeline --audio song.mp3 --cover cover.png --lyrics lyrics.srt --output output/
```

When no lyrics are supplied, OpenMuse uses existing project lyrics or an installed ASR provider. It never invents lyrics when no source is available.

## Architecture

```text
apps/web                 Next.js workspace
apps/api/openmuse_api    FastAPI API, jobs, storage, and services
packages/timeline        LRC, SRT, VTT, and ASS timeline tools
packages/providers       Mock, MiniMax, and custom provider adapters
templates                Music video templates
cli                      openmuse command-line interface
tests                    Unit, API, and media tests
```

```text
INGEST -> ANALYZE -> LYRICS -> GENERATE -> ALIGN -> SUBTITLE -> RENDER -> VALIDATE
```

## Development

```bash
make setup
make test
make lint
make render-demo
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
```

Optional local capabilities:

```bash
uv sync --extra asr
uv sync --extra audio-ml
uv sync --extra all
```

## Privacy and Copyright

Only upload material you own or are authorized to use. OpenMuse does not provide public-figure voice presets or tools to bypass watermarks, copyright detection, or access controls. Third-party providers may apply their own data policies.

Do not commit API keys, private settings, commercial music, or large model files.

## Contributing

Keep changes focused, preserve provider capability flags, add tests for behavior changes, and run the media render smoke test before opening a pull request.

OpenMuse Studio is licensed under Apache-2.0.
