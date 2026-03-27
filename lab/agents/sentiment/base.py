"""Base class for sentiment agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum

import pandas as pd


class SentimentDirection(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass
class SentimentEvent:
    """Output from a sentiment agent."""
    sentiment: SentimentDirection
    score: float
    confidence: float
    sources: list[str] = field(default_factory=list)
    indicators: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class BaseSentimentAgent(ABC):
    """Abstract base class for sentiment agents.
    
    Sentiment agents analyze news, social media, and other
    alternative data to gauge market sentiment.
    """

    def __init__(self, symbol: str = "SYNTHETIC", **kwargs):
        self.symbol = symbol
        self._params = kwargs

    @abstractmethod
    def analyze(self, symbol: str) -> SentimentEvent:
        """Analyze sentiment for a symbol.
        
        Args:
            symbol: Asset symbol to analyze
            
        Returns:
            SentimentEvent with sentiment direction, score, and confidence
        """
        ...
