"""Shared base class and SignalEvent for all signal agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum

import pandas as pd


class SignalDirection(Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass
class SignalEvent:
    """Output from any signal agent."""
    asset: str
    direction: SignalDirection
    strength: float
    confidence: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    indicators: dict = field(default_factory=dict)


class BaseSignalAgent(ABC):
    """Abstract base class for all signal agents.
    
    All signal agents must implement `generate(df) -> SignalEvent`.
    """

    def __init__(self, symbol: str = "SYNTHETIC", **kwargs):
        self.symbol = symbol
        self._params = kwargs

    @abstractmethod
    def generate(self, df: pd.DataFrame) -> SignalEvent:
        """Generate a signal from the latest bar(s) in the dataframe.
        
        Args:
            df: DataFrame with OHLCV columns (Open, High, Low, Close, Volume)
                Must have at least enough bars for all indicator lookbacks.
                
        Returns:
            SignalEvent with direction, strength, confidence, and indicators
        """
        ...

    def generate_all(self, df: pd.DataFrame) -> pd.Series:
        """Pre-compute signals for all bars (vectorized).
        
        Default implementation calls generate() per bar — override for performance.
        Returns a Series of SignalDirection values aligned to df.index.
        """
        from lab.agents.signal.base import SignalDirection
        signals = []
        for i in range(len(df)):
            lookback = df.iloc[: i + 1]
            signal = self.generate(lookback)
            signals.append(signal.direction)
        return pd.Series(signals, index=df.index)

    def _get_latest(self, df: pd.DataFrame, col: str) -> float:
        """Get the latest value of a column."""
        return float(df[col].iloc[-1])

    def _require_cols(self, df: pd.DataFrame, required: list[str]) -> None:
        """Verify required columns exist in dataframe."""
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Missing columns: {missing}")
