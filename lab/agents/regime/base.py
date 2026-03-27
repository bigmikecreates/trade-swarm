"""Base class for regime agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum

import pandas as pd


class MarketRegime(Enum):
    BULL_TREND = "bull_trend"
    BEAR_TREND = "bear_trend"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    CONSOLIDATION = "consolidation"
    UNKNOWN = "unknown"


@dataclass
class RegimeEvent:
    """Output from a regime agent."""
    regime: MarketRegime
    confidence: float
    indicators: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class BaseRegimeAgent(ABC):
    """Abstract base class for regime detection agents.
    
    Regime agents classify the current market state to help
    other agents adjust their behavior accordingly.
    """

    def __init__(self, symbol: str = "SYNTHETIC", **kwargs):
        self.symbol = symbol
        self._params = kwargs

    @abstractmethod
    def classify(self, df: pd.DataFrame) -> RegimeEvent:
        """Classify the current market regime.
        
        Args:
            df: DataFrame with OHLCV columns
            
        Returns:
            RegimeEvent with regime classification and confidence
        """
        ...
