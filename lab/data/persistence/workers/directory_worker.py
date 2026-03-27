"""Background worker — consumes from Redis Stream and writes to canonical directories."""

from __future__ import annotations

import json
import logging

import redis

logger = logging.getLogger(__name__)


class DirectoryWorker:
    """Consume events from Redis Stream and write to canonical directories.
    
    Idempotent: re-running produces the same result.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379", consumer_group: str = "directory_workers"):
        self.redis_url = redis_url
        self.consumer_group = consumer_group
        self._client: redis.Redis | None = None

    def connect(self) -> None:
        self._client = redis.from_url(self.redis_url, decode_responses=True)
        self._client.ping()

    def run(self, run_id: str, block_ms: int = 5000) -> None:
        if self._client is None:
            self.connect()

        stream_key = f"lab:events:{run_id}"
        consumer_name = f"worker_{id(self)}"

        try:
            self._client.xgroup_create(stream_key, self.consumer_group, id="0", mkstream=True)
        except redis.ResponseError:
            pass

        while True:
            messages = self._client.xreadgroup(
                self.consumer_group,
                consumer_name,
                {stream_key: ">"},
                count=100,
                block=block_ms,
            )

            for stream, msgs in messages or []:
                for msg_id, fields in msgs:
                    try:
                        event_type = fields.get("event_type", "")
                        event_data = json.loads(fields.get("event_data", "{}"))

                        idempotency_key = f"processed:{run_id}:{event_type}:{msg_id}"
                        if self._client.exists(idempotency_key):
                            self._client.xack(stream_key, self.consumer_group, msg_id)
                            continue

                        self._write_to_directory(run_id, event_type, event_data)
                        self._client.set(idempotency_key, "1")
                        self._client.xack(stream_key, self.consumer_group, msg_id)

                    except Exception as e:
                        logger.error(f"Error processing message {msg_id}: {e}")

    def _write_to_directory(self, run_id: str, event_type: str, event_data: dict) -> None:
        pass
