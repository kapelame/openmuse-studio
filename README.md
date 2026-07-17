# OpenMuse Studio

一个开源 AI 音乐工作台：从文字、歌词、Demo 或歌曲生成音乐、同步歌词、封面和音乐视频。

<p align="center">
  <a href="https://codespaces.new/kapelame/openmuse-studio?quickstart=1"><img src="https://github.com/codespaces/badge.svg" alt="在 GitHub Codespaces 中启动" /></a>
  <a href="#使用-docker-启动"><img src="https://img.shields.io/badge/使用%20Docker%20启动-2496ED?logo=docker&logoColor=white" alt="使用 Docker 启动" /></a>
</p>

## 核心能力

- 从文字、歌词、哼唱、Demo 或现有歌曲开始创作。
- 上传音频、封面和歌词，生成稳定的同步歌词音乐视频。
- 导出 MP4、字幕、封面和项目清单。
- 默认使用本地模拟 Provider；配置后可使用 MiniMax。

## 当前状态

已经可以运行：

- 项目创建、素材上传、歌词编辑和任务进度查询。
- 1:1、16:9、9:16、4:5 视频渲染。
- FFmpeg 音视频合成、ASS 字幕和 contact sheet 生成。
- Mock Provider、MiniMax Provider、运行时设置和命令行工具。
- 17 个自动化测试。

默认未启用：

- faster-whisper、WhisperX、Demucs、Basic Pitch 等大型本地能力。
- 完整多轨编辑器、真正的续写、音色转换和人声分离生成。
- 多用户认证和生产级对象存储。

## 快速启动

### GitHub Codespaces

点击页面顶部的 **Open in GitHub Codespaces** 按钮。环境会自动安装依赖并启动工作台。

### 本地启动

要求：Python 3.11+、Node 20.9+、FFmpeg 和 ffprobe。

```bash
git clone https://github.com/kapelame/openmuse-studio.git
cd openmuse-studio
./start.sh
```

打开 `http://localhost:3000`。

首次在本地终端启动时，程序会询问是否配置 MiniMax。输入 API Key 时使用隐藏输入，也可以直接回车使用 Mock Provider。重新打开设置问询：

```bash
./start.sh --setup
```

### 使用 Docker 启动

```bash
docker compose up --build
```

打开 `http://localhost:3000`。停止服务：

```bash
docker compose down
```

如果端口被占用：

```bash
OPENMUSE_WEB_PORT=3001 OPENMUSE_API_PORT=8001 docker compose up --build
```

## MiniMax 配置

可以在安装问询、网页设置面板或 `.env` 中配置：

```dotenv
MINIMAX_API_KEY=
MINIMAX_API_BASE=https://api.minimaxi.com
MINIMAX_MUSIC_MODEL=music-3.0
MINIMAX_COVER_MODEL=music-cover
DEFAULT_MUSIC_PROVIDER=minimax
```

当前音乐生成接口推荐使用 `music-3.0`，同时支持 `music-2.6` 和限免版本。模型名称始终通过环境变量或设置面板配置，不写死在前端代码中。

MiniMax 返回的临时音频地址会立即下载到项目存储。Key 不会进入前端、数据库、项目清单或普通日志。

## 运行时设置

启动后点击左侧 **Providers** 或顶部 **Settings**，可以随时修改：

- 默认音乐 Provider 和图片 Provider。
- MiniMax API Base、音乐模型和封面模型。
- Custom HTTP 地址。
- 本地 ASR、Demucs、Basic Pitch 开关。

设置保存在 `.openmuse/settings.json`，文件权限为 `0600`，并且不会提交到 Git。

## 可选音频能力

默认安装不下载大型模型。按需安装：

```bash
uv sync --extra asr
uv sync --extra audio-ml
uv sync --extra all
```

没有 ASR 能力时，系统不会虚构歌词；原始歌词也不会被 ASR 静默覆盖。

## 命令行

```bash
openmuse analyze AUDIO
openmuse transcribe AUDIO
openmuse align AUDIO LYRICS
openmuse render --audio song.mp3 --cover cover.png --lyrics lyrics.srt --output output/
openmuse pipeline --audio song.mp3 --cover cover.png --lyrics lyrics.srt --output output/
```

## 架构

```text
apps/web                 Next.js 网页工作台
apps/api/openmuse_api    FastAPI 接口、数据库和任务
packages/timeline        LRC、SRT、VTT、ASS 时间轴工具
packages/providers       Provider 接口、Mock、MiniMax
templates                音乐视频模板
cli                      openmuse 命令行工具
tests                    单元测试、接口测试和媒体测试
```

处理流程：

```text
INGEST -> ANALYZE -> LYRICS -> GENERATE -> ALIGN -> SUBTITLE -> RENDER -> VALIDATE
```

## 版权与隐私

上传 Demo 或歌曲前，必须确认拥有素材版权或获得授权。项目不提供公众人物音色预设，不绕过水印、版权识别或权限校验。第三方 Provider 可能有独立的数据政策。

## 测试

```bash
make test
make lint
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
make render-demo
```

## 贡献

请保持改动聚焦，保留 Provider 能力标记，增加对应测试，并在提交前运行完整媒体渲染。不要提交 API Key、商业音乐或大型模型文件。
