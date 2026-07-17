"""Redis-backed worker for long-running OpenMuse jobs."""

from __future__ import annotations

import json
import time

import redis

from .config import settings
from .db import db, utc_now
from .main import analyze_audio_job_sync, render_job_sync


def main() -> None:
    client = redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=5, socket_timeout=30)
    client.ping()
    print(f"OpenMuse worker ready on {settings.redis_queue_name}")
    while True:
        item = client.brpop(settings.redis_queue_name, timeout=5)
        if not item:
            continue
        payload = json.loads(item[1])
        job_id = payload["job_id"]
        job = db._one("SELECT status FROM jobs WHERE id=?", (job_id,))
        if not job or job["status"] == "cancelled":
            continue
        try:
            if payload["kind"] == "render_video":
                render_job_sync(payload["project_id"], payload["render_id"], job_id, payload["request"])
            elif payload["kind"] == "analyze_audio":
                analyze_audio_job_sync(payload["project_id"], payload["asset_id"], job_id)
            else:
                raise RuntimeError(f"Unsupported job kind: {payload['kind']}")
        except Exception as exc:
            db.update("jobs", job_id, {"status": "failed", "progress": 100, "error_code": "WORKER_FAILED", "error_message": str(exc), "finished_at": utc_now()})


if __name__ == "__main__":
    main()
