# Architecture Notes

The local path is intentionally dependency-light: FastAPI + SQLite + local filesystem + FFmpeg. Docker includes PostgreSQL, Redis and MinIO so a deployment can replace the adapters without changing the product surface.

Long-running operations are represented by `Job` rows. The API pushes render and analysis payloads to Redis when available and falls back to FastAPI `BackgroundTasks` for local development. The worker consumes the same queue and invokes the same service functions, so Web and CLI do not fork the pipeline. Every job has status, progress, attempts, logs, error code/message and timestamps.

The render service never concatenates shell commands. It passes an argv array to `subprocess.run`, probes media with ffprobe, uses integer dimensions, forces yuv420p, H.264/AAC, 24 or 30fps and caps output duration to the source audio duration.
