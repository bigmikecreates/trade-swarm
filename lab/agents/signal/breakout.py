"""Breakout signal agent using Donchian Channels and ATR.

Generates LONG when price breaks above the upper Donchian Channel with expanding ATR
  (momentum confirmation — volatility is increasing).
Generates SHORT when price breaks below the lower Donchian Channel with expanding ATR.
Generates FLAT when price is within the channel or ATR is contracting.

Parameters:
    dc_length (int): Donchian Channel period (default: 20)
    atr_length (int): ATR period (default: 14)
    atr_expansion_threshold (float): Min ATR increase to confirm breakout (default: 1.2)
"""

from __future__ import annotations

import pandas as pd

from lab.agents.signal.base import BaseSignalAgent, SignalEvent, SignalDirection
from lab.agents.signal.indicators import donchian_channels, atr


class BreakoutSignalAgent(BaseSignalAgent):
    """Donchian Channel breakout strategy with ATR confirmation."""

    STRATEGIES = {
        "donchian_atr": "Donchian + ATR confirmation",
        "donchian_only": "Donchian Channel only",
        "range_expansion": "Range expansion breakout",
    }

    def __init__(
        self,
        symbol: str = "SYNTHETIC",
        dc_length: int = 20,
        atr_length: int = 14,
        atr_expansion_threshold: float = 1.2,
        strategy: str = "donchian_atr",
        **kwargs,
    ):
        super().__init__(symbol=symbol, **kwargs)
        self.dc_length = dc_length
        self.atr_length = atr_length
        self.atr_expansion_threshold = atr_expansion_threshold
        self.strategy = strategy

    def generate(self, df: pd.DataFrame) -> SignalEvent:
        self._require_cols(df, ["High", "Low", "Close"])

        df = df.copy()
        high = df["High"]
        low = df["Low"]
        close = df["Close"]

        dc_upper, dc_middle, dc_lower = donchian_channels(high, low, self.dc_length)
        df["DC_upper"] = dc_upper
        df["DC_lower"] = dc_lower
        df["ATR"] = atr(high, low, close, self.atr_length)
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

        close_val = last["Close"]
        dc_upper_val = last["DC_upper"]
        dc_lower_val = last["DC_lower"]
        dc_mid_val = last["DC_lower"] + (last["DC_upper"] - last["DC_lower"]) / 2
        atr_val = last["ATR"]
        atr_prev_val = prev["ATR"]
        prev_close = prev["Close"]

        bullish_breakout = prev_close <= prev["DC_upper"] and close_val > dc_upper_val
        bearish_breakout = prev_close >= prev["DC_lower"] and close_val < dc_lower_val
        atr_expanding = atr_val > (atr_prev_val * self.atr_expansion_threshold)

        if self.strategy == "donchian_atr":
            if bullish_breakout and atr_expanding:
                direction = SignalDirection.LONG
            elif bearish_breakout and atr_expanding:
                direction = SignalDirection.SHORT
            else:
                direction = SignalDirection.FLAT
        elif self.strategy == "donchian_only":
            if bullish_breakout:
                direction = SignalDirection.LONG
            elif bearish_breakout:
                direction = SignalDirection.SHORT
            else:
                direction = SignalDirection.FLAT
        else:
            direction = SignalDirection.FLAT

        if direction == SignalDirection.FLAT:
            strength = 0.0
            confidence = 0.0
        else:
            channel_width = dc_upper_val - dc_lower_val
            breakout_size = abs(close_val - (dc_upper_val if direction == SignalDirection.LONG else dc_lower_val))
            strength = min(breakout_size / channel_width, 1.0) if channel_width > 0 else 0.0
            atr_ratio = atr_val / atr_prev_val if atr_prev_val > 0 else 1.0
            confidence = min(atr_ratio / 2.0, 1.0)

        return SignalEvent(
            asset=self.symbol,
            direction=direction,
            strength=round(strength, 4),
            confidence=round(confidence, 4),
            indicators={
                "dc_upper": round(dc_upper_val, 6),
                "dc_lower": round(dc_lower_val, 6),
                "atr": round(atr_val, 6),
                "atr_ratio": round(atr_val / atr_prev_val, 4) if atr_prev_val > 0 else 1.0,
                "close": round(close_val, 6),
                "breakout": "bullish" if bullish_breakout else ("bearish" if bearish_breakout else "none"),
            },
        )

    def generate_all(self, df: pd.DataFrame) -> pd.Series:
        """Pre-compute signals for all bars (vectorized)."""
        from lab.agents.signal.indicators import donchian_channels, atr

        high = df["High"]
        low = df["Low"]
        close = df["Close"]

        dc_upper, _, dc_lower = donchian_channels(high, low, self.dc_length)
        atr_series = atr(high, low, close, self.atr_length)

        prev_close = close.shift(1)
        prev_dc_upper = dc_upper.shift(1)
        prev_dc_lower = dc_lower.shift(1)
        prev_atr = atr_series.shift(1)

        bullish_breakout = (prev_close <= prev_dc_upper) & (close > dc_upper)
        bearish_breakout = (prev_close >= prev_dc_lower) & (close < dc_lower)
        atr_expanding = atr_series > (prev_atr * self.atr_expansion_threshold)

        longs = bullish_breakout & atr_expanding
        shorts = bearish_breakout & atr_expanding

        signals = pd.Series(SignalDirection.FLAT, index=df.index)
        signals[longs] = SignalDirection.LONG
        signals[shorts] = SignalDirection.SHORT
        return signals
