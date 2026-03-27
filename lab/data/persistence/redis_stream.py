"""Redis Stream producer — agents write events here first."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import redis


class RedisStreamProducer:
    """Write agent events to Redis Stream.
    
    The Redis Stream acts as the real-time event buffer.
    Workers consume from here and write to PostgreSQL and directories.
    
    Stream key pattern: lab:events:{run_id}
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self._client: redis.Redis | None = None
        self._retention_hours = 72

    def connect(self) -> None:
        self._client = redis.from_url(self.redis_url, decode_responses=True)
        self._client.ping()

    def publish(self, run_id: str, event_type: str, event_data: dict) -> None:
        if self._client is None:
            self.connect()

        stream_key = f"lab:events:{run_id}"
        message = {
            "event_type": event_type,
            "event_data": json.dumps(event_data),
            "timestamp": datetime.utcnow().isoformat(),
        }

        self._client.xadd(stream_key, message, maxlen=10000, approx=True)
        self._client.expire(stream_key, self._retention_hours * 3600)

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
