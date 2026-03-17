"""Activate the kill switch — blocks all new trades until manually reset."""

import redis
from config import REDIS_URL

if __name__ == "__main__":
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
        r.ping()
        r.set("kill_switch", "1")
        print("⛔ Kill switch activated. All trading is halted.")
        print("To reset: redis-cli DEL kill_switch")
    except (redis.ConnectionError, redis.TimeoutError) as e:
        print(f"❌ Redis unavailable: {e}")
