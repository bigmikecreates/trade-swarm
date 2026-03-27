"""Momentum signal agent using Rate of Change (ROC) and MACD.

Generates LONG when ROC is positive and rising (strong upward momentum).
Generates SHORT when ROC is negative and falling (strong downward momentum).
Generates FLAT when momentum is weakening or neutral.

Parameters:
    roc_length (int): ROC period (default: 12)
    roc_threshold (float): Minimum ROC to signal (default: 1.0)
    macd_fast (int): MACD fast period (default: 12)
    macd_slow (int): MACD slow period (default: 26)
    macd_signal (int): MACD signal period (default: 9)
"""

from __future__ import annotations

import pandas as pd

from lab.agents.signal.base import BaseSignalAgent, SignalEvent, SignalDirection
from lab.agents.signal.indicators import roc, macd, ema


class MomentumSignalAgent(BaseSignalAgent):
    """Rate of Change momentum strategy with MACD confirmation."""

    STRATEGIES = {
        "roc_macd": "ROC + MACD confirmation",
        "roc_only": "ROC only",
        "macd_histogram": "MACD histogram divergence",
    }

    def __init__(
        self,
        symbol: str = "SYNTHETIC",
        roc_length: int = 12,
        roc_threshold: float = 1.0,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        strategy: str = "roc_macd",
        **kwargs,
    ):
        super().__init__(symbol=symbol, **kwargs)
        self.roc_length = roc_length
        self.roc_threshold = roc_threshold
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.strategy = strategy

    def generate(self, df: pd.DataFrame) -> SignalEvent:
        self._require_cols(df, ["Close"])

        df = df.copy()
        close = df["Close"]

        df["ROC"] = roc(close, self.roc_length)
        macd_line, signal_line, histogram = macd(
            close, self.macd_fast, self.macd_slow, self.macd_signal
        )
        df["MACD_line"] = macd_line
        df["MACD_signal"] = signal_line
        df["MACD_hist"] = histogram
        df["EMA_5"] = ema(close, 5)
        df["EMA_20"] = ema(close, 20)
        df["momentum_rising"] = df["ROC"] > df["ROC"].shift(1)
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
        roc_val = last["ROC"]
        roc_prev_val = prev["ROC"]
        macd_val = last["MACD_line"]
        macd_signal_val = last["MACD_signal"]
        hist_val = last["MACD_hist"]
        hist_prev_val = prev["MACD_hist"]
        ema_5_val = last["EMA_5"]
        ema_20_val = last["EMA_20"]

        roc_positive = roc_val > self.roc_threshold
        roc_negative = roc_val < -self.roc_threshold
        roc_rising = roc_val > roc_prev_val
        roc_falling = roc_val < roc_prev_val
        macd_bullish = macd_val > macd_signal_val
        macd_bearish = macd_val < macd_signal_val
        hist_expanding_up = hist_val > hist_prev_val
        hist_expanding_down = hist_val < hist_prev_val
        ema_bullish = ema_5_val > ema_20_val
        ema_bearish = ema_5_val < ema_20_val

        if self.strategy == "roc_macd":
            if roc_positive and roc_rising and macd_bullish and ema_bullish:
                direction = SignalDirection.LONG
            elif roc_negative and roc_falling and macd_bearish and ema_bearish:
                direction = SignalDirection.SHORT
            else:
                direction = SignalDirection.FLAT
        elif self.strategy == "roc_only":
            if roc_positive and roc_rising:
                direction = SignalDirection.LONG
            elif roc_negative and roc_falling:
                direction = SignalDirection.SHORT
            else:
                direction = SignalDirection.FLAT
        elif self.strategy == "macd_histogram":
            if macd_bullish and hist_expanding_up:
                direction = SignalDirection.LONG
            elif macd_bearish and hist_expanding_down:
                direction = SignalDirection.SHORT
            else:
                direction = SignalDirection.FLAT
        else:
            direction = SignalDirection.FLAT

        if direction == SignalDirection.FLAT:
            strength = 0.0
            confidence = 0.0
        else:
            abs_roc = abs(roc_val)
            strength = min(abs_roc / 10.0, 1.0)
            confirm_count = 0
            if self.strategy == "roc_macd":
                confirm_count = sum([
                    abs(roc_val) > self.roc_threshold,
                    macd_bullish if direction == SignalDirection.LONG else macd_bearish,
                    ema_bullish if direction == SignalDirection.LONG else ema_bearish,
                ])
                confidence = confirm_count / 3.0
            else:
                confidence = min(abs_roc / 5.0, 1.0)

        return SignalEvent(
            asset=self.symbol,
            direction=direction,
            strength=round(strength, 4),
            confidence=round(confidence, 4),
            indicators={
                "roc": round(roc_val, 4),
                "macd_line": round(macd_val, 6),
                "macd_signal": round(macd_signal_val, 6),
                "macd_histogram": round(hist_val, 6),
                "ema_5": round(ema_5_val, 6),
                "ema_20": round(ema_20_val, 6),
                "close": round(close_val, 6),
            },
        )

    def generate_all(self, df: pd.DataFrame) -> pd.Series:
        """Pre-compute signals for all bars (vectorized)."""
        from lab.agents.signal.indicators import roc, macd, ema

        close = df["Close"]
        roc_series = roc(close, self.roc_length)
        macd_line, signal_line, histogram = macd(
            close, self.macd_fast, self.macd_slow, self.macd_signal
        )
        ema_5 = ema(close, 5)
        ema_20 = ema(close, 20)

        roc_rising = roc_series > roc_series.shift(1)
        roc_falling = roc_series < roc_series.shift(1)
        macd_bullish = macd_line > signal_line
        macd_bearish = macd_line < signal_line
        ema_bullish = ema_5 > ema_20
        ema_bearish = ema_5 < ema_20

        longs = (roc_series > self.roc_threshold) & roc_rising & macd_bullish & ema_bullish
        shorts = (roc_series < -self.roc_threshold) & roc_falling & macd_bearish & ema_bearish

        signals = pd.Series(SignalDirection.FLAT, index=df.index)
        signals[longs] = SignalDirection.LONG
        signals[shorts] = SignalDirection.SHORT
        return signals
