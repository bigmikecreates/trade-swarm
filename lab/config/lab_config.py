"""Lab-wide configuration."""

from __future__ import annotations

import os
from pathlib import Path

LAB_ROOT = Path(__file__).parent.parent
EXPERIMENTS_DIR = LAB_ROOT / "experiments"
SYNTHETIC_CONFIGS_DIR = LAB_ROOT / "synthetic" / "configs"

CLEANUP_TTL_DAYS = 5
REDIS_STREAM_RETENTION_HOURS = 72
DEFAULT_INIT_CASH = 10_000.0
DEFAULT_FEE_RATE = 0.001
DEFAULT_RISK_PCT = 0.01

POSTGRES_HOST = os.environ.get("LAB_POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.environ.get("LAB_POSTGRES_PORT", "5432"))
POSTGRES_DB = os.environ.get("LAB_POSTGRES_DB", "trade_swarm_lab")
POSTGRES_USER = os.environ.get("LAB_POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.environ.get("LAB_POSTGRES_PASSWORD", "")

REDIS_URL = os.environ.get("LAB_REDIS_URL", "redis://localhost:6379")

AVAILABLE_DATA_SOURCES = [
    "synthetic",
    "yfinance",
    "ctrader_ic_markets",
    "ctrader_pepperstone",
    "ctrader_eightcap",
    "histdata",
    "ibkr",
]

AVAILABLE_STRATEGIES = [
    "trend_signal",
    "mean_reversion",
    "breakout",
    "momentum",
    "full_coordination",
]

AVAILABLE_AGENTS = [
    "trend_signal",
    "mean_reversion",
    "breakout",
    "momentum",
    "risk",
    "regime",
    "execution",
    "sentiment",
]
