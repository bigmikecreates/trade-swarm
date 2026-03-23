"""Append-only JSONL log of paper-trading loop activity (signals, gate, errors).

Each line is one JSON object. Do not edit or delete lines in production — append only.
Path: data/agent_activity.jsonl
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Repo root = parent of this package (logging/)
ACTIVITY_PATH = Path(__file__).resolve().parents[1] / "data" / "agent_activity.jsonl"


def init_activity_log() -> None:
    """Ensure data directory exists (file is created on first log_activity)."""
    ACTIVITY_PATH.parent.mkdir(parents=True, exist_ok=True)


def log_activity(event: str, **fields: Any) -> None:
    """
    Append one JSON object as a single line (JSONL). Thread-safe enough for
    single-threaded paper loop; add a lock if multiple writers later.
    """
    init_activity_log()
    record: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **{k: _sanitize(v) for k, v in fields.items()},
    }
    line = json.dumps(record, default=str, ensure_ascii=False) + "\n"
    with open(ACTIVITY_PATH, "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()


def _sanitize(v: Any) -> Any:
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v
