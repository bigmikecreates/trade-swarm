"""Basic risk gate — 4 rules only. Full gate in v0.5.0."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

import redis


class RedisUnavailableError(Exception):
    """Raised when Redis is not reachable. Start Redis or check REDIS_URL."""


class GateResult(Enum):
    PASS = "pass"
    BLOCK = "block"
    HALT = "halt"


@dataclass
class GateDecision:
    result: GateResult
    rule: str | None
    reason: str | None
    timestamp: datetime


class BasicRiskGate:
    """
    v0.2.0 gate — 4 rules only.
    Full gate implemented in v0.5.0.
    """

    def __init__(self, account_equity: float, redis_url: str = "redis://localhost:6379"):
        self.equity = account_equity
        self.daily_start = account_equity
        try:
            self.r = redis.from_url(redis_url, decode_responses=True)
            self.r.ping()
        except (redis.ConnectionError, redis.TimeoutError) as e:
            raise RedisUnavailableError(
                f"Redis unavailable at {redis_url}. Start Redis (e.g. redis-server) or set REDIS_URL. {e}"
            ) from e

    def _safe_redis(self, op, default=None):
        """Run Redis op; on failure return default (HALT for get, no-op for set)."""
        try:
            return op()
        except (redis.ConnectionError, redis.TimeoutError):
            return default

    def check(self, order: dict, current_equity: float) -> GateDecision:
        # Rule 1: kill switch (on Redis failure, treat as HALT for safety)
        kill = self._safe_redis(lambda: self.r.get("kill_switch"), "1")
        if kill == "1":
            return GateDecision(
                GateResult.HALT,
                "kill_switch",
                "Kill switch active",
                datetime.utcnow(),
            )

        # Rule 2: daily loss limit (3%)
        daily_loss = (self.daily_start - current_equity) / self.daily_start
        if daily_loss >= 0.03:
            return GateDecision(
                GateResult.HALT,
                "daily_loss",
                f"Down {daily_loss:.1%} today",
                datetime.utcnow(),
            )

        # Rule 3: max position size (10% of account)
        notional = order.get("size", 0) * order.get("price", 0)
        pos_pct = notional / current_equity if current_equity > 0 else 1.0
        if pos_pct > 0.10:
            return GateDecision(
                GateResult.BLOCK,
                "max_position",
                f"Order is {pos_pct:.1%} of account",
                datetime.utcnow(),
            )

        # Rule 4: duplicate order check
        asset = order.get("asset")
        existing_dir = self._safe_redis(
            lambda: self.r.get(f"position_direction:{asset}"),
            order.get("direction"),  # On Redis failure, assume duplicate → block
        )
        if (
            existing_dir
            and existing_dir == order.get("direction")
            and order.get("action") == "enter"
        ):
            return GateDecision(
                GateResult.BLOCK,
                "duplicate",
                f"Already {existing_dir} {asset}",
                datetime.utcnow(),
            )

        return GateDecision(GateResult.PASS, None, None, datetime.utcnow())

    def activate_kill_switch(self):
        try:
            self.r.set("kill_switch", "1")
            print("⛔ Kill switch activated")
        except (redis.ConnectionError, redis.TimeoutError):
            print("⚠️ Redis unavailable — kill switch not persisted. Restart Redis and try again.")

    def reset_daily(self, current_equity: float):
        """Call this at market open each day."""
        self.daily_start = current_equity

    def set_position_direction(self, asset: str, direction: str | None):
        """Track position direction for duplicate check. None = clear."""
        key = f"position_direction:{asset}"
        try:
            if direction is None:
                self.r.delete(key)
            else:
                self.r.set(key, direction)
        except (redis.ConnectionError, redis.TimeoutError):
            pass  # Best-effort; duplicate check may be stale
