"""Technical indicators (pure pandas, no numba)."""

import pandas as pd
import numpy as np


def ema(series: pd.Series, length: int) -> pd.Series:
    """Exponential moving average."""
    return series.ewm(span=length, adjust=False).mean()


def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.inf)
    return 100 - (100 / (1 + rs))


def adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    """Average Directional Index."""
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1 / length, adjust=False).mean()

    plus_di = 100 * (plus_dm.ewm(alpha=1 / length, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / length, adjust=False).mean() / atr)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    return dx.ewm(alpha=1 / length, adjust=False).mean()
