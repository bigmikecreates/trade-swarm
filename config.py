"""Configuration for v0.1.0 trading system."""

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
