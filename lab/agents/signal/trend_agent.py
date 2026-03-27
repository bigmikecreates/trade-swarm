"""Trend-following signal agent using EMA crossover with ADX filter.

Generates LONG when fast EMA crosses above slow EMA with strong trend (ADX > threshold).
Generates SHORT when fast EMA crosses below slow EMA with strong trend.
Generates FLAT when ADX < threshold (weak trend) or no crossover.

Parameters:
    ema_fast (int): Fast EMA period (default: 8)
    ema_slow (int): Slow EMA period (default: 21)
    adx_threshold (float): Minimum ADX for valid trend signal (default: 25.0)
"""

from __future__ import annotations

import pandas as pd
import numpy as np

from lab.agents.signal.base import BaseSignalAgent, SignalEvent, SignalDirection
from lab.agents.signal.indicators import ema, adx, rsi


class TrendSignalAgent(BaseSignalAgent):
    """EMA crossover trend-following strategy."""

    STRATEGIES = {
        "ema_cross": "EMA crossover",
        "macd": "MACD-based crossover",
        "adx_filtered": "ADX-filtered crossover",
    }

    def __init__(
        self,
        symbol: str = "SYNTHETIC",
        ema_fast: int = 8,
        ema_slow: int = 21,
        adx_threshold: float = 25.0,
        strategy: str = "adx_filtered",
        **kwargs,
    ):
        super().__init__(symbol=symbol, **kwargs)
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.adx_threshold = adx_threshold
        self.strategy = strategy

    def generate(self, df: pd.DataFrame) -> SignalEvent:
        self._require_cols(df, ["High", "Low", "Close"])

        df = df.copy()
        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        df["EMA_fast"] = ema(close, self.ema_fast)
        df["EMA_slow"] = ema(close, self.ema_slow)
        df["ADX"] = adx(high, low, close, 14)
        df["RSI"] = rsi(close, 14)
        df.dropna(inplace=True)

        if len(df) < 2:
            return SignalEvent(
                asset=self.symbol,
                direction=SignalDirection.FLAT,
                strength=0.0,
                confidence=0.0,
                indicators={},
            )

        last = df.iloc[-1]
        prev = df.iloc[-2]

        ema_fast_val = last["EMA_fast"]
        ema_slow_val = last["EMA_slow"]
        prev_fast = prev["EMA_fast"]
        prev_slow = prev["EMA_slow"]
        adx_val = last["ADX"]
        rsi_val = last["RSI"]
        close_val = last["Close"]

        bullish_cross = prev_fast <= prev_slow and ema_fast_val > ema_slow_val
        bearish_cross = prev_fast >= prev_slow and ema_fast_val < ema_slow_val
        strong_trend = adx_val >= self.adx_threshold

        if self.strategy == "adx_filtered":
            if bullish_cross and strong_trend:
                direction = SignalDirection.LONG
            elif bearish_cross and strong_trend:
                direction = SignalDirection.SHORT
            else:
                direction = SignalDirection.FLAT
        elif self.strategy == "ema_cross":
            if bullish_cross:
                direction = SignalDirection.LONG
            elif bearish_cross:
                direction = SignalDirection.SHORT
            else:
                direction = SignalDirection.FLAT
        else:
            direction = SignalDirection.FLAT

        if direction == SignalDirection.FLAT:
            strength = 0.0
            confidence = 0.0
        else:
            spread = abs(ema_fast_val - ema_slow_val) / ema_slow_val
            strength = min(spread * 1000, 1.0)
            confidence = min(adx_val / 50.0, 1.0)

        return SignalEvent(
            asset=self.symbol,
            direction=direction,
            strength=round(strength, 4),
            confidence=round(confidence, 4),
            indicators={
                "ema_fast": round(ema_fast_val, 6),
                "ema_slow": round(ema_slow_val, 6),
                "adx": round(adx_val, 2),
                "rsi": round(rsi_val, 2),
                "close": round(close_val, 6),
                "crossover": "bullish" if bullish_cross else ("bearish" if bearish_cross else "none"),
            },
        )

    def generate_all(self, df: pd.DataFrame) -> pd.Series:
        """Pre-compute signals for all bars (vectorized)."""
        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        ema_fast_series = ema(close, self.ema_fast)
        ema_slow_series = ema(close, self.ema_slow)
        adx_series = adx(high, low, close, 14)

        bullish_cross = (ema_fast_series.shift(1) <= ema_slow_series.shift(1)) & (
            ema_fast_series > ema_slow_series
        )
        bearish_cross = (ema_fast_series.shift(1) >= ema_slow_series.shift(1)) & (
            ema_fast_series < ema_slow_series
        )
        strong_trend = adx_series >= self.adx_threshold

        if self.strategy == "adx_filtered":
            longs = bullish_cross & strong_trend
            shorts = bearish_cross & strong_trend
        elif self.strategy == "ema_cross":
            longs = bullish_cross
            shorts = bearish_cross
        else:
            longs = pd.Series(False, index=df.index)
            shorts = pd.Series(False, index=df.index)

        signals = pd.Series(SignalDirection.FLAT, index=df.index)
        signals[longs] = SignalDirection.LONG
        signals[shorts] = SignalDirection.SHORT

        return signals
