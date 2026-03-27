"""Technical indicators for signal agents — pure pandas, no external indicators library."""

from __future__ import annotations

import pandas as pd
import numpy as np


def ema(series: pd.Series, length: int) -> pd.Series:
    """Exponential moving average."""
    return series.ewm(span=length, adjust=False).mean()


def sma(series: pd.Series, length: int) -> pd.Series:
    """Simple moving average."""
    return series.rolling(length).mean()


def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.inf)
    return 100 - (100 / (1 + rs))


def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    """Average True Range."""
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / length, adjust=False).mean()


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

    atr_val = tr.ewm(alpha=1 / length, adjust=False).mean()

    plus_di = 100 * (plus_dm.ewm(alpha=1 / length, adjust=False).mean() / atr_val)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / length, adjust=False).mean() / atr_val)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    return dx.ewm(alpha=1 / length, adjust=False).mean()


def bollinger_bands(series: pd.Series, length: int = 20, num_std: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Bollinger Bands — returns (upper, middle, lower)."""
    middle = sma(series, length)
    std = series.rolling(length).std()
    upper = middle + (std * num_std)
    lower = middle - (std * num_std)
    return upper, middle, lower


def donchian_channels(high: pd.Series, low: pd.Series, length: int = 20) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Donchian Channels — returns (upper, middle, lower)."""
    upper = high.rolling(length).max()
    middle = (upper + low.rolling(length).min()) / 2
    lower = low.rolling(length).min()
    return upper, middle, lower


def roc(series: pd.Series, length: int = 12) -> pd.Series:
    """Rate of Change — percentage change over period."""
    return 100 * (series - series.shift(length)) / series.shift(length)


def stochastic(high: pd.Series, low: pd.Series, close: pd.Series, k_length: int = 14, d_length: int = 3) -> tuple[pd.Series, pd.Series]:
    """Stochastic Oscillator — returns (%K, %D)."""
    lowest_low = low.rolling(k_length).min()
    highest_high = high.rolling(k_length).max()
    k = 100 * (close - lowest_low) / (highest_high - lowest_low)
    d = k.rolling(d_length).mean()
    return k, d


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD — returns (macd_line, signal_line, histogram)."""
    fast_ema = ema(series, fast)
    slow_ema = ema(series, slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram
