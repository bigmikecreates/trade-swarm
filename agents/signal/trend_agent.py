"""Trend-following signal agent using EMA crossover and ADX."""

import pandas as pd
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from data.indicators import ema, adx, rsi
from data.regime import Regime, detect_regimes


class Direction(Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass
class SignalEvent:
    asset: str
    direction: Direction
    strength: float  # 0.0 – 1.0
    confidence: float  # 0.0 – 1.0
    timestamp: datetime
    indicators: dict


class TrendSignalAgent:
    def __init__(
        self,
        symbol: str,
        use_regime: bool = False,
        ema_fast: int = 20,
        ema_slow: int = 50,
    ):
        self.symbol = symbol
        self.use_regime = use_regime
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow

    def generate(self, df: pd.DataFrame) -> SignalEvent:
        df = df.copy()
        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        df["EMA_fast"] = ema(close, self.ema_fast)
        df["EMA_slow"] = ema(close, self.ema_slow)
        df["ADX_14"] = adx(high, low, close, 14)
        df["RSI_14"] = rsi(close, 14)

        regime_val = None
        if self.use_regime:
            regimes = detect_regimes(df)
            df = df.loc[regimes.index]
            df["regime"] = regimes
            regime_val = df["regime"].iloc[-1].value

        df.dropna(inplace=True)

        last = df.iloc[-1]
        ema_fast_val = last["EMA_fast"]
        ema_slow_val = last["EMA_slow"]
        adx_val = last["ADX_14"]
        rsi_val = last["RSI_14"]

        if ema_fast_val > ema_slow_val:
            direction = Direction.LONG
        elif ema_fast_val < ema_slow_val:
            direction = Direction.SHORT
        else:
            direction = Direction.FLAT

        # If regime filter is active and market isn't trending, go FLAT
        if self.use_regime and regime_val != Regime.TRENDING.value:
            direction = Direction.FLAT

        strength = min(abs(ema_fast_val - ema_slow_val) / ema_slow_val * 100, 1.0)
        confidence = min(adx_val / 50, 1.0)

        indicators = {
            "ema_fast": ema_fast_val,
            "ema_slow": ema_slow_val,
            "adx": adx_val,
            "rsi": rsi_val,
        }
        if regime_val is not None:
            indicators["regime"] = regime_val

        return SignalEvent(
            asset=self.symbol,
            direction=direction,
            strength=round(strength, 4),
            confidence=round(confidence, 4),
            timestamp=datetime.utcnow(),
            indicators=indicators,
        )
