from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis_async

from ..config import settings


class QueueUnavailable(RuntimeError):
    pass


def _client() -> redis_async.Redis:
    return redis_async.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=0.35, socket_timeout=0.35)


async def enqueue(payload: dict[str, Any]) -> None:
    client = _client()
    try:
        await client.ping()
        await client.rpush(settings.redis_queue_name, json.dumps(payload, separators=(",", ":")))
    except Exception as exc:
        raise QueueUnavailable(str(exc)) from exc
    finally:
        await client.aclose()


async def mark_cancelled(job_id: str) -> None:
    client = _client()
    try:
        await client.set(f"openmuse:cancelled:{job_id}", "1", ex=86400)
    except Exception:
        return
    finally:
        await client.aclose()


async def clear_cancelled(job_id: str) -> None:
    client = _client()
    try:
        await client.delete(f"openmuse:cancelled:{job_id}")
    except Exception:
        return
    finally:
        await client.aclose()
