"""Configuration for v0.1.0 / v0.2.0 trading system."""

import os
from pathlib import Path

# Load .env from project root if present (for paper trading secrets)
_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except ImportError:
        pass  # python-dotenv optional; use export or system env

# Alpaca paper trading (v0.2.0) — prefer env vars, fallback to empty
ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY", "")
ALPACA_BASE_URL = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
PAPER_TRADING = True
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")

# Paper trading loop
PAPER_SYMBOL = os.environ.get("PAPER_SYMBOL", "SPY")  # Override via .env; SPY validated in v0.1.0
PAPER_EMA_FAST = 8    # Validated for SPY (v0.1.0)
PAPER_EMA_SLOW = 21   # Validated for SPY (v0.1.0)
PAPER_CHECK_INTERVAL = 300  # seconds (5 min)
PAPER_PERIOD = "60d"
PAPER_INTERVAL = "1d"  # Daily matches v0.1.0 validated strategy

# Backtest defaults
DEFAULT_SYMBOL = "EURUSD=X"
DEFAULT_PERIOD = "2y"
DEFAULT_INTERVAL = "1h"
INIT_CASH = 10_000
FEE_RATE = 0.001  # 0.1% per trade

# EMA parameters
EMA_FAST = 20
EMA_SLOW = 50

# Regime filter — only enter trades when ADX indicates a trend
ADX_PERIOD = 14
ADX_THRESHOLD = 25  # minimum ADX to allow entries (0 = disabled)

# Gate thresholds
GATE_MIN_SHARPE = 0.8
GATE_MAX_DRAWDOWN_PCT = 20.0
GATE_MIN_TRADES = 30  # reject results with too few trades (overfitting risk)
