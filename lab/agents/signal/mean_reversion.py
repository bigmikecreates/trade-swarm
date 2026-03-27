"""Mean reversion signal agent using RSI and Bollinger Bands.

Generates LONG when price is near lower Bollinger Band and RSI < oversold threshold
  (mean reversion signal — price has deviated below fair value).
Generates SHORT when price is near upper Bollinger Band and RSI > overbought threshold
  (mean reversion signal — price has deviated above fair value).
Generates FLAT when price is within Bollinger Bands or RSI is neutral.

Parameters:
    rsi_length (int): RSI period (default: 14)
    rsi_oversold (float): RSI oversold threshold (default: 30.0)
    rsi_overbought (float): RSI overbought threshold (default: 70.0)
    bb_length (int): Bollinger Band period (default: 20)
    bb_std (float): Bollinger Band standard deviations (default: 2.0)
    band_proximity (float): How close to band triggers signal (default: 0.95)
"""

from __future__ import annotations

import pandas as pd

from lab.agents.signal.base import BaseSignalAgent, SignalEvent, SignalDirection
from lab.agents.signal.indicators import rsi, bollinger_bands


class MeanReversionSignalAgent(BaseSignalAgent):
    """RSI + Bollinger Bands mean reversion strategy."""

    STRATEGIES = {
        "rsi_bb": "RSI + Bollinger Bands",
        "rsi_only": "RSI only",
        "stochastic_bb": "Stochastic + Bollinger Bands",
    }

    def __init__(
        self,
        symbol: str = "SYNTHETIC",
        rsi_length: int = 14,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        bb_length: int = 20,
        bb_std: float = 2.0,
        band_proximity: float = 0.95,
        strategy: str = "rsi_bb",
        **kwargs,
    ):
        super().__init__(symbol=symbol, **kwargs)
        self.rsi_length = rsi_length
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.bb_length = bb_length
        self.bb_std = bb_std
        self.band_proximity = band_proximity
        self.strategy = strategy

    def generate(self, df: pd.DataFrame) -> SignalEvent:
        self._require_cols(df, ["Close"])

        df = df.copy()
        close = df["Close"]

        df["RSI"] = rsi(close, self.rsi_length)
        bb_upper, bb_middle, bb_lower = bollinger_bands(close, self.bb_length, self.bb_std)
        df["BB_upper"] = bb_upper
        df["BB_middle"] = bb_middle
        df["BB_lower"] = bb_lower
        df["BB_position"] = (close - bb_lower) / (bb_upper - bb_lower)
        df.dropna(inplace=True)

        if len(df) < 1:
            return SignalEvent(
                asset=self.symbol,
                direction=SignalDirection.FLAT,
                strength=0.0,
                confidence=0.0,
                indicators={},
            )

        last = df.iloc[-1]
        close_val = last["Close"]
        rsi_val = last["RSI"]
        bb_upper_val = last["BB_upper"]
        bb_lower_val = last["BB_lower"]
        bb_mid_val = last["BB_middle"]
        bb_pos_val = last["BB_position"]

        if self.strategy in ("rsi_bb", "stochastic_bb"):
            near_lower = bb_pos_val <= self.band_proximity
            near_upper = bb_pos_val >= (1.0 - self.band_proximity)
            rsi_oversold = rsi_val <= self.rsi_oversold
            rsi_overbought = rsi_val >= self.rsi_overbought

            if near_lower and rsi_oversold:
                direction = SignalDirection.LONG
            elif near_upper and rsi_overbought:
                direction = SignalDirection.SHORT
            else:
                direction = SignalDirection.FLAT
        elif self.strategy == "rsi_only":
            if rsi_val <= self.rsi_oversold:
                direction = SignalDirection.LONG
            elif rsi_val >= self.rsi_overbought:
                direction = SignalDirection.SHORT
            else:
                direction = SignalDirection.FLAT
        else:
            direction = SignalDirection.FLAT

        if direction == SignalDirection.FLAT:
            strength = 0.0
            confidence = 0.0
        else:
            deviation = abs(close_val - bb_mid_val) / (bb_upper_val - bb_lower_val)
            strength = min(deviation, 1.0)
            extreme = abs(rsi_val - 50) / 50
            confidence = min(extreme, 1.0)

        return SignalEvent(
            asset=self.symbol,
            direction=direction,
            strength=round(strength, 4),
            confidence=round(confidence, 4),
            indicators={
                "rsi": round(rsi_val, 2),
                "bb_upper": round(bb_upper_val, 6),
                "bb_middle": round(bb_mid_val, 6),
                "bb_lower": round(bb_lower_val, 6),
                "bb_position": round(bb_pos_val, 4),
                "close": round(close_val, 6),
            },
        )

    def generate_all(self, df: pd.DataFrame) -> pd.Series:
        """Pre-compute signals for all bars (vectorized)."""
        from lab.agents.signal.indicators import rsi, bollinger_bands

        close = df["Close"]
        rsi_series = rsi(close, self.rsi_length)
        bb_upper, bb_middle, bb_lower = bollinger_bands(close, self.bb_length, self.bb_std)
        bb_pos = (close - bb_lower) / (bb_upper - bb_lower)

        near_lower = bb_pos <= self.band_proximity
        near_upper = bb_pos >= (1.0 - self.band_proximity)
        rsi_oversold = rsi_series <= self.rsi_oversold
        rsi_overbought = rsi_series >= self.rsi_overbought

        longs = near_lower & rsi_oversold
        shorts = near_upper & rsi_overbought

        signals = pd.Series(SignalDirection.FLAT, index=df.index)
        signals[longs] = SignalDirection.LONG
        signals[shorts] = SignalDirection.SHORT
        return signals
