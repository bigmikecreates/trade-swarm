"""Base class for risk agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum

import pandas as pd


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskEvent:
    """Output from a risk agent."""
    risk_level: RiskLevel
    max_position_pct: float
    var_95: float | None = None
    drawdown_pct: float | None = None
    heat_pct: float | None = None
    warnings: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class BaseRiskAgent(ABC):
    """Abstract base class for all risk agents.
    
    Risk agents evaluate portfolio risk and return position limits.
    """

    def __init__(self, symbol: str = "SYNTHETIC", **kwargs):
        self.symbol = symbol
        self._params = kwargs

    @abstractmethod
    def evaluate(self, df: pd.DataFrame, equity: float, position: float | None, 
                 entry_price: float | None) -> RiskEvent:
        """Evaluate current risk and return position limits.
        
        Args:
            df: DataFrame with OHLCV columns
            equity: Current portfolio equity
            position: Current position size (None if flat)
            entry_price: Entry price of current position
            
        Returns:
            RiskEvent with risk_level, max_position_pct, and warnings
        """
        ...
